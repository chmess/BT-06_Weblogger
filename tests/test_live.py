import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.common.bt06 import MANUFACTURER_ID, advertised_reading, decode
from backend.common.live_store import LiveStore, LIVE_FIELDS
from backend.common.storage import chart_data, csv_text
from backend.linux.receiver import Receiver
from backend.linux.ble_jobs import BluetoothJobs, BusyError


def frame(temperature=201, humidity=550, unit=0, device_id="12345678"):
    data = bytearray(24)
    data[:3] = b"\x09\x02\x05"
    data[4:8] = bytes.fromhex(device_id)
    data[11], data[12], data[14] = 100, 2, unit
    for offset, value in ((15, temperature), (17, humidity)):
        encoded = abs(value) | (0x8000 if value < 0 else 0)
        data[offset:offset+2] = encoded.to_bytes(2, "little")
    return bytes(data)


def config():
    return {"schema_version": 1, "enabled": True, "device": {"id": "12345678", "address": "AA:BB:CC:DD:EE:FF", "firmware": "2.05", "name": "Synthetic test logger"},
            "adapter": "hci0", "save_interval_seconds": 60}


class DecoderTests(unittest.TestCase):
    def test_protocol_vectors_sign_units_and_status(self):
        value = decode(frame(-123, 654))
        self.assertEqual(value.temperature_c, -12.3)
        self.assertEqual(value.humidity_pct, 65.4)
        self.assertEqual(value.voltage_v, 3)
        self.assertEqual(value.firmware, "2.05")
        self.assertEqual(value.recording, "zeichnet auf")
        self.assertAlmostEqual(decode(frame(680, 500, unit=1)).temperature_c, 20)
        data = bytearray(frame())
        data[12], data[13] = 0x27, 0x0B
        value = decode(data)
        self.assertTrue(value.memory_full)
        self.assertEqual(value.lock_level, 2)
        self.assertEqual(value.temperature_alarm, 3)
        self.assertEqual(value.humidity_alarm, 2)
        self.assertEqual(value.recording, "gestoppt")

    def test_unknown_and_invalid_never_become_measurements(self):
        for payload in (b"", frame()[:18], bytes([8])+frame()[1:], frame()[:1]+b"\x03\x00"+frame()[3:]):
            with self.assertRaises(ValueError):
                decode(payload)
            self.assertIsNone(advertised_reading({MANUFACTURER_ID: payload}))
        self.assertIsNone(decode(frame(unit=3)).temperature_c)
        data = bytearray(frame());data[16] = 0xFE
        self.assertIsNone(decode(data).temperature_c)
        self.assertIsNone(decode(frame(humidity=1001)).humidity_pct)
        self.assertEqual(decode(frame(humidity=0)).humidity_pct, 0)


class ReceiverStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = LiveStore(self.root / "data")
        self.receiver = Receiver(self.root / "config/receiver.json", self.store, threading.Lock())
        self.receiver.config = config()
        self.device = SimpleNamespace(address=config()["device"]["address"])
        self.advertisement = SimpleNamespace(manufacturer_data={MANUFACTURER_ID: frame()}, rssi=-55)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def test_every_packet_updates_live_but_csv_is_throttled_and_missing_stays_missing(self):
        self.receiver.on_advertisement(self.device, self.advertisement, self.now)
        self.advertisement.manufacturer_data = {MANUFACTURER_ID: frame(215, 600)}
        self.receiver.on_advertisement(self.device, self.advertisement, self.now + timedelta(seconds=30))
        self.assertEqual(self.receiver.status()["latest"]["temperature_c"], 21.5)
        self.assertEqual(self.receiver.status()["saved_this_session"], 1)
        self.receiver.on_advertisement(self.device, self.advertisement, self.now + timedelta(seconds=61))
        rows = list(self.store.rows("bt06-12345678"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["Zeitbasis"], "Host-Empfang")
        self.assertEqual(rows[-1]["Quelle"], "BLE-Advertising")
        self.assertEqual(rows[-1]["Batterie"], "")
        self.assertEqual(rows[-1]["Batteriespannung"], "3,00")
        self.assertEqual(self.store.latest("bt06-12345678"), rows[-1])
        self.assertNotEqual(rows[0]["DatensatzID"], rows[1]["DatensatzID"])
        self.assertIn("Batteriespannung", csv_text(rows, LIVE_FIELDS))
        self.assertEqual(chart_data(iter(rows), 1)["raw_count"], 2)

    def test_identity_mismatch_and_foreign_device_are_not_saved(self):
        wrong = SimpleNamespace(address="11:22:33:44:55:66")
        self.receiver.on_advertisement(wrong, self.advertisement, self.now)
        self.advertisement.manufacturer_data = {MANUFACTURER_ID: frame(device_id="87654321")}
        self.receiver.on_advertisement(self.device, self.advertisement, self.now)
        self.assertEqual(list(self.store.rows("bt06-12345678")), [])
        self.assertIn("Geräteidentität", self.receiver.status()["error"])

    def test_failed_write_not_acknowledged_and_retry_succeeds(self):
        with patch.object(self.store, "append", side_effect=OSError("disk full")):
            self.receiver.on_advertisement(self.device, self.advertisement, self.now)
        self.assertEqual(self.receiver.status()["saved_this_session"], 0)
        self.assertIsNone(self.receiver.status()["last_stored_at"])
        self.assertIn("CSV-Schreibfehler", self.receiver.status()["error"])
        self.receiver.on_advertisement(self.device, self.advertisement, self.now + timedelta(seconds=1))
        self.assertEqual(self.receiver.status()["saved_this_session"], 1)

    def test_corrupt_tail_preserved_and_reporting_survives_restart(self):
        self.receiver.on_advertisement(self.device, self.advertisement, self.now)
        path = next((self.root / "data").glob("*/*/*.csv"))
        with path.open("ab") as out:
            out.write(b"partial")
        original = path.read_bytes()
        self.receiver.on_advertisement(self.device, self.advertisement, self.now + timedelta(seconds=61))
        self.assertEqual(path.read_bytes(), original)
        self.assertIn("Unvollständige", self.receiver.status()["error"])
        self.receiver.config_path.parent.mkdir(exist_ok=True)
        self.receiver.config_path.write_text(json.dumps(config()))
        restarted = Receiver(self.receiver.config_path, self.store, threading.Lock())
        self.assertIn("CSV", restarted.status()["error"])

    def test_backward_clock_never_appends_out_of_order(self):
        self.receiver.on_advertisement(self.device, self.advertisement, self.now)
        self.receiver.on_advertisement(self.device, self.advertisement, self.now - timedelta(seconds=60))
        self.assertEqual(len(list(self.store.rows("bt06-12345678"))), 1)
        self.assertIn("Host-Uhr", self.receiver.status()["error"])

    def test_unknown_sensor_values_create_gaps(self):
        for offset, unit in ((0, 0), (60, 3), (120, 0)):
            self.advertisement.manufacturer_data = {MANUFACTURER_ID: frame(unit=unit)}
            self.receiver.on_advertisement(self.device, self.advertisement, self.now + timedelta(seconds=offset))
        data = chart_data(self.store.rows("bt06-12345678"), 1)
        self.assertTrue(any(row[1] is None and row[2] is None for row in data["points"]))
        missing = [{"Zeitstempel": (self.now + timedelta(minutes=i)).isoformat(), "Temperatur": "", "Feuchte": ""} for i in range(5000)]
        self.assertLess(len(chart_data(iter(missing), 1)["points"]), 10)

    def test_explicit_receiver_owns_radio_and_shutdown_preserves_resume_intent(self):
        ready = threading.Event()
        calls = []
        test = self
        class Scanner:
            def __init__(self, **kwargs):
                import inspect
                test.assertEqual(len(inspect.signature(kwargs["detection_callback"]).parameters), 2)
                test.assertEqual(kwargs["bluez"], {"adapter": "hci0", "filters": {"DuplicateData": True}})
                self.callback = kwargs["detection_callback"]
                calls.append("scanner")
            async def __aenter__(self):
                self.callback(test.device, test.advertisement)
                ready.set()
                return self
            async def __aexit__(self, *args):
                calls.append("scanner_closed")
        with patch.dict("sys.modules", {"bleak": SimpleNamespace(BleakScanner=Scanner)}):
            self.receiver.start(config())
            self.assertTrue(ready.wait(timeout=3))
            manager = BluetoothJobs(self.receiver.radio_lock)
            with self.assertRaises(BusyError):
                manager.start({"command": "scan"})
            self.receiver.stop(persist=False)
        self.assertTrue(json.loads(self.receiver.config_path.read_text())["enabled"])
        self.assertEqual(calls, ["scanner", "scanner_closed"])
        self.assertEqual(self.receiver.status()["saved_this_session"], 1)
        self.receiver.stop(persist=True)
        self.assertFalse(json.loads(self.receiver.config_path.read_text())["enabled"])
        self.assertTrue(self.receiver.radio_lock.acquire(blocking=False))
        self.receiver.radio_lock.release()


if __name__ == "__main__":
    unittest.main()
