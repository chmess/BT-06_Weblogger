import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.linux.ble_diagnose import diagnose
from backend.linux.ble_jobs import BluetoothJobs, BusyError


class BluetoothTests(unittest.TestCase):
    def test_no_pairing_without_explicit_request_and_no_characteristic_access(self):
        device = SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="Synthetic test logger")
        advertisement = SimpleNamespace(local_name="Synthetic test logger", rssi=-50, service_uuids=[], manufacturer_data={}, service_data={})
        calls = []
        class Scanner:
            @staticmethod
            async def discover(**kwargs):
                calls.append(("scan", kwargs))
                return {device.address: (device, advertisement)}
            @staticmethod
            async def find_device_by_address(address, **kwargs):
                calls.append(("find", kwargs))
                return device if address == device.address else None
        class Client:
            def __init__(self, target, **kwargs):
                calls.append(("connect", kwargs))
                self.services = [SimpleNamespace(uuid="test-service", characteristics=[SimpleNamespace(uuid="test-characteristic", properties=["read"], descriptors=[])])]
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                calls.append(("disconnect", {}))
        with patch.dict("sys.modules", {"bleak": SimpleNamespace(BleakScanner=Scanner, BleakClient=Client)}):
            for pair in (False, True):
                calls.clear()
                args = SimpleNamespace(command="gatt", seconds=1, adapter="hci1", device=device.address, pair=pair)
                result = asyncio.run(diagnose(args))
                self.assertEqual(calls[0][1]["bluez"], {"adapter": "hci1", "filters": {"DuplicateData": True}})
                self.assertEqual(calls[1][0], "connect")
                self.assertEqual(calls[1][1]["pair"], pair)
                self.assertEqual(calls[-1][0], "disconnect")
                self.assertFalse(result["connected"])
                self.assertEqual(result["pairing_requested"], pair)
            calls.clear()
            args.command = "scan"
            result = asyncio.run(diagnose(args))
            self.assertEqual([call[0] for call in calls], ["scan"])
            self.assertTrue(calls[0][1]["bluez"]["filters"]["DuplicateData"])
            self.assertEqual(result["devices"][0]["rssi"], -50)

    def test_jobs_require_discovery_and_are_serialized(self):
        manager = BluetoothJobs()
        with self.assertRaises(ValueError):
            manager.start({"command": "gatt", "device": "AA:BB:CC:DD:EE:FF", "pair": True})
        with self.assertRaises(ValueError):
            manager.start({"command": "scan", "pair": True})
        async def scan(args):
            await asyncio.sleep(.1)
            return {"devices": [{"address": "AA:BB:CC:DD:EE:FF"}]}
        with patch("backend.linux.ble_jobs.diagnose", scan):
            manager.start({"command": "scan", "adapter": "hci1", "seconds": 1})
            with self.assertRaises(BusyError):
                manager.start({"command": "scan"})
            manager.worker.join(2)
        self.assertEqual(manager.status()["state"], "done")
        with self.assertRaises(ValueError):
            manager.start({"command": "gatt", "adapter": "hci0", "device": "AA:BB:CC:DD:EE:FF"})
        seen = []
        async def gatt(args):
            seen.append(args.pair)
            return {"connected": False}
        with patch("backend.linux.ble_jobs.diagnose", gatt):
            manager.start({"command": "gatt", "adapter": "hci1", "device": "AA:BB:CC:DD:EE:FF"})
            manager.worker.join(2)
        self.assertEqual(seen, [False])


if __name__ == "__main__":
    unittest.main()
