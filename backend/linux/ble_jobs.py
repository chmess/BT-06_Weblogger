"""One explicit BLE job at a time. No startup scan, pairing or background reconnect."""
import asyncio
import importlib.util
import re
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from .ble_diagnose import diagnose


class BusyError(RuntimeError):
    pass


class BluetoothJobs:
    def __init__(self):
        self.lock = threading.Lock()
        self.worker = None
        self.value = {"state": "idle", "command": None, "result": None, "error": None}
        self.candidates = {}

    def status(self):
        with self.lock:
            return {**deepcopy(self.value), "available": importlib.util.find_spec("bleak") is not None,
                    "adapters": sorted(path.name for path in Path("/sys/class/bluetooth").glob("hci*"))}

    def start(self, options):
        if not isinstance(options, dict) or set(options) - {"command", "adapter", "seconds", "device", "pair"}:
            raise ValueError("Ungültige Bluetooth-Optionen.")
        command = options.get("command")
        adapter = options.get("adapter", "hci0")
        seconds = options.get("seconds", 10)
        pair = options.get("pair", False)
        if command not in ("scan", "gatt") or not isinstance(adapter, str) or not re.fullmatch(r"hci[0-9]{1,3}", adapter):
            raise ValueError("Ungültiger Bluetooth-Auftrag.")
        if type(seconds) is not int or not 1 <= seconds <= 30 or type(pair) is not bool:
            raise ValueError("Ungültiger Timeout oder Kopplungswert.")
        if command == "scan" and (pair or options.get("device")):
            raise ValueError("Suche darf weder koppeln noch verbinden.")
        with self.lock:
            if self.value["state"] == "running":
                raise BusyError("Ein Bluetooth-Auftrag läuft bereits.")
            device = options.get("device")
            if command == "gatt" and (not isinstance(device, str) or self.candidates.get(device) != adapter):
                raise ValueError("Gerät zuerst auf diesem Adapter suchen und bewusst auswählen.")
            self.value = {"state": "running", "command": command, "result": None, "error": None}
            if command == "scan":
                self.candidates = {}
            args = SimpleNamespace(command=command, adapter=adapter, seconds=seconds, device=device, pair=pair)
            self.worker = threading.Thread(target=self._run, args=(args,), name="bt06-ble-job")
            self.worker.start()
        return self.status()

    def _run(self, args):
        try:
            result = asyncio.run(asyncio.wait_for(diagnose(args), timeout=args.seconds + 45))
            with self.lock:
                if args.command == "scan":
                    self.candidates = {item["address"]: args.adapter for item in result["devices"]}
                self.value.update(state="done", result=result)
        except Exception as exc:
            # No raw OS/DBus error payloads: they can contain device identifiers.
            if isinstance(exc, RuntimeError) and "Bleak fehlt" in str(exc):
                message = "Bleak fehlt. Optional mit ./install.sh --ble installieren."
            elif isinstance(exc, TimeoutError):
                message = "Bluetooth-Zeitlimit erreicht. Gerät kann sichtbar sein, ohne eine GATT-Verbindung anzunehmen. Andere App-Verbindungen und den vom Hersteller beschriebenen Verbindungsmodus prüfen. Keine Logger-Konfiguration wurde ausgeführt."
            elif isinstance(exc, RuntimeError) and "nicht gefunden" in str(exc):
                message = "Ausgewähltes Gerät während der Suche nicht gefunden. Erneut suchen und Reichweite prüfen."
            else:
                message = "Bluetooth-Auftrag fehlgeschlagen. Adapter und BlueZ-Berechtigungen prüfen. Für Kopplung ggf. einen systemeigenen BlueZ-Agent verwenden."
            with self.lock:
                self.value.update(state="error", error=message)
