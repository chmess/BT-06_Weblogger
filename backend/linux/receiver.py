"""User-enabled BLE advertising receiver; never connects, pairs or writes to a logger."""
import asyncio
import json
import math
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone

from backend.common.bt06 import advertised_reading
from backend.common.settings import atomic_json
from backend.common.storage import parse_time
from .ble_jobs import BusyError
from .ble_options import scan_options


class Receiver:
    def __init__(self, config_path, store, radio_lock, events=None, warnings=None):
        self.warnings=warnings
        self.events=events;self._reported_error=None;self._fresh_state=None;self._last_recording=None;self._last_full=None
        self.config_path = config_path
        self.store = store
        self.radio_lock = radio_lock
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.worker = None
        self.config = {"schema_version": 1, "enabled": False, "device": None, "adapter": "hci0", "save_interval_seconds": 60}
        if config_path.exists():
            value = json.loads(config_path.read_text(encoding="utf-8"))
            self.validate(value)
            self.config = value
        self.value = {"state": "stopped", "latest": None, "saved_this_session": 0,
                      "last_stored_at": None, "error": None, "received_packets": 0}
        if self.config["device"]:
            try:
                latest = store.latest("bt06-" + self.config["device"]["id"])
                if latest:
                    self.value["last_stored_at"] = latest["Zeitstempel"]
            except (OSError, ValueError):
                self.value["error"] = "Letzte Live-CSV konnte nicht gelesen werden. Originaldatei erhalten."

    @staticmethod
    def validate(value):
        if not isinstance(value, dict) or set(value) != {"schema_version", "enabled", "device", "adapter", "save_interval_seconds"}:
            raise ValueError("Ungültige Empfangskonfiguration.")
        if value["schema_version"] != 1 or type(value["enabled"]) is not bool:
            raise ValueError("Unbekannte Empfangskonfiguration.")
        if not isinstance(value["adapter"], str) or not re.fullmatch(r"hci[0-9]{1,3}", value["adapter"]):
            raise ValueError("Ungültiger Bluetooth-Adapter.")
        interval = value["save_interval_seconds"]
        if type(interval) is not int or not 10 <= interval <= 3600:
            raise ValueError("Speicherabstand muss zwischen 10 und 3600 Sekunden liegen.")
        device = value["device"]
        if device is not None:
            if not isinstance(device, dict) or set(device) != {"address", "id", "firmware", "name"}:
                raise ValueError("Ungültige Empfangsgerätekennung.")
            if not isinstance(device["id"], str) or not re.fullmatch(r"[0-9]{8}", device["id"]):
                raise ValueError("Ungültige BT06-Kennung.")
            if not isinstance(device["address"], str) or not re.fullmatch(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}", device["address"]):
                raise ValueError("Ungültige BLE-Adresse.")
            if device["firmware"] != "2.05" or not isinstance(device["name"], str) or len(device["name"]) > 80:
                raise ValueError("Geräteformat noch nicht verifiziert.")
        if value["enabled"] and device is None:
            raise ValueError("Empfang benötigt ein bewusst ausgewähltes Gerät.")

    def status(self):
        with self.lock:
            result = {**deepcopy(self.value), "config": deepcopy(self.config), "gatt_connected": False}
        latest = result["latest"]
        age = (datetime.now(timezone.utc) - parse_time(latest["received_at"])).total_seconds() if latest else None
        result["age_seconds"] = round(age, 1) if age is not None else None
        result["fresh"] = age is not None and 0 <= age <= 90
        return result

    def _event(self,event_type,level,message,details=None,at=None):
        if self.events:
            selected=self.config['device']
            self.events.emit(event_type,level,message,source='receiver',logger='bt06-'+selected['id'] if selected else '',details=details,at=at)

    def _report_error(self):
        error=self.value['error']
        if error and error!=self._reported_error:self._event('receiver.error','error',error)
        elif not error and self._reported_error:self._event('receiver.recovered','info','Empfang und CSV-Speicherung wieder erfolgreich.')
        self._reported_error=error

    def _advert_events(self,reading,received):
        if not self.events:return
        stamp=received.isoformat()
        if self._fresh_state is not True:self._event('receiver.fresh','info','Gültiges aktuelles Advertising empfangen; keine GATT-Verbindung.',at=stamp)
        self._fresh_state=True
        if reading['recording']!=self._last_recording:
            self._event('device.recording','info','Advertising meldet Aufzeichnungsstatus: '+reading['recording'],at=stamp)
            self._last_recording=reading['recording']
        full=reading['memory_full']
        if full and self._last_full is not True:self._event('device.memory_full','warning','Gerät meldet Speichervollkennzeichnung.',at=stamp)
        elif not full and self._last_full is True:self._event('device.memory_full','info','Speichervollkennzeichnung aufgehoben; freie Kapazität bleibt unbekannt.',at=stamp)
        self._last_full=full

    def check_health(self,now=None):
        if self.warnings:self.warnings.tick(now)
        if not self.events:return
        with self.lock:
            if self.stop_event.is_set() or self.value['state']!='receiving' or self._fresh_state is not True:return
            latest=self.value['latest'];stamp=now or datetime.now(timezone.utc)
            age=(stamp-parse_time(latest['received_at'])).total_seconds() if latest else None
            if age is None or not 0<=age<=90:
                self._fresh_state=False
                self._event('receiver.stale','warning','Keine aktuelle Aussendung im 90-Sekunden-Fenster; kein Nachweis eines Gerätestopps.',at=stamp.isoformat())

    def start(self, config=None):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise BusyError("Liveempfang läuft bereits. Vor Gerätewechsel pausieren.")
            selected = deepcopy(config or self.config)
            selected["enabled"] = True
            self.validate(selected)
            if not self.radio_lock.acquire(blocking=False):
                raise BusyError("Bluetooth ist noch durch einen Diagnoseauftrag belegt.")
            try:
                atomic_json(self.config_path, selected)
                changed_device = self.config["device"] != selected["device"]
                self.config = selected
                if changed_device:
                    self._last_recording=self._last_full=None
                    self.value.update(latest=None, last_stored_at=None)
                    stored = self.store.latest("bt06-" + selected["device"]["id"])
                    if stored:
                        self.value["last_stored_at"] = stored["Zeitstempel"]
                self.stop_event.clear();self._fresh_state=None
                self.value.update(state="starting", error=None)
                self.worker = threading.Thread(target=self._run, name="bt06-advertising")
                self.worker.start()
            except BaseException:
                self.radio_lock.release()
                raise
        self._event('receiver.started','info','Hostempfang gestartet; Loggeraufzeichnung unverändert.')
        return self.status()

    def stop(self, persist=True):
        with self.lock:
            if persist:
                value = {**self.config, "enabled": False}
                atomic_json(self.config_path, value)
                self.config = value
            self.stop_event.set()
            worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=8)
        if self.warnings:self.warnings.pause()
        if persist:self._event('receiver.stopped','info','Hostempfang pausiert; kein Stoppbefehl an den Logger.')
        return self.status()

    def on_advertisement(self, device, advertisement, now=None):
        received = now or datetime.now(timezone.utc)
        with self.lock:
            selected = self.config["device"]
            if self.stop_event.is_set() or not selected or device.address.lower() != selected["address"].lower():
                return
            reading = advertised_reading(advertisement.manufacturer_data)
            if not reading:
                self.value["error"] = "Advertising-Format nicht verifiziert. Kein Messwert gespeichert."
                self._report_error()
                return
            if reading["device_id"] != selected["id"]:
                self.value["error"] = "Geräteidentität stimmt nicht. Kein Messwert gespeichert."
                self._report_error()
                return
            self._advert_events(reading,received)
            self.value["received_packets"] += 1
            self.value["latest"] = {**reading, "rssi": advertisement.rssi, "received_at": received.isoformat()}
            last = self.value["last_stored_at"]
            elapsed = (received - parse_time(last)).total_seconds() if last else None
            if elapsed is not None and elapsed < 0:
                self.value["error"] = "Host-Uhr liegt vor dem letzten gespeicherten Empfang. CSV-Schreiben pausiert."
                self._report_error()
                return
            if elapsed is not None and elapsed < self.config["save_interval_seconds"]:
                return
            try:
                stored_row=self.store.append(reading, advertisement.rssi, received.isoformat())
            except (OSError, ValueError) as exc:
                self.value["error"] = str(exc) if isinstance(exc, ValueError) else "CSV-Schreibfehler: Speicherplatz und Dateirechte prüfen. Empfang ist nicht dauerhaft gespeichert."
                self._report_error()
                return
            if self.warnings:self.warnings.observe("bt06-"+selected["id"],stored_row,self.config["save_interval_seconds"])
            self.value["last_stored_at"] = received.isoformat()
            self.value["saved_this_session"] += 1
            self.value["error"] = None
            self._report_error()

    async def _listen(self):
        from bleak import BleakScanner
        def received(device, advertisement):
            self.on_advertisement(device, advertisement)
        delay = 1
        while not self.stop_event.is_set():
            try:
                async with BleakScanner(detection_callback=received, bluez=scan_options(self.config["adapter"])):
                    with self.lock:
                        self.value["state"] = "receiving"
                    delay = 1
                    while not self.stop_event.is_set():
                        await asyncio.sleep(.2)
                        self.check_health()
            except Exception:
                if self.warnings:self.warnings.pause("receiver_interrupted")
                with self.lock:
                    self.value.update(state="retrying", error="BLE-Empfang unterbrochen. Erneuter Versuch; Loggeraufzeichnung bleibt unverändert.")
                    self._report_error()
                for _ in range(delay * 5):
                    if self.stop_event.is_set():
                        break
                    await asyncio.sleep(.2)
                delay = min(delay * 2, 30)

    def _run(self):
        try:
            asyncio.run(self._listen())
        except Exception:
            with self.lock:
                self.value.update(state="error", error="BLE-Umgebung nicht verfügbar. Bleak, BlueZ und Berechtigungen prüfen.")
                self._report_error()
        finally:
            with self.lock:
                if self.value["state"] != "error":
                    self.value["state"] = "stopped"
            self.radio_lock.release()
