import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from backend.linux.history_reader import known_device
from backend.common.bt06 import MANUFACTURER_ID
from test_live import frame
from test_history_jobs import config


class DiscoveryTests(unittest.TestCase):
    def test_cache_and_fresh_discovery_match_selected_adapter_identity_and_firmware(self):
        selected=config();address=selected['device']['address']
        for cached in (False,True):
            calls=[];props={key:SimpleNamespace(value=value) for key,value in {'Address':address,'Adapter':'/org/bluez/hci0','Connected':False}.items()}
            class Bus:
                def __init__(self,**kwargs):pass
                async def connect(self):return self
                async def call(self,message):return SimpleNamespace(message_type='ok',body=[{'/selected':{'org.bluez.Device1':props}} if cached else {}])
                def disconnect(self):calls.append('bus_closed')
            class Device:
                def __init__(self,address,name,details):self.address=address;self.details=details
            class Scanner:
                @staticmethod
                async def find_device_by_filter(predicate,**options):
                    calls.append('scan');test.assertEqual(options['bluez'],{'adapter':'hci0','filters':{'DuplicateData':True}})
                    device=Device(address,'Synthetic',{})
                    test.assertFalse(predicate(Device('00:00:00:00:00:01','Other',{}),SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame()})))
                    test.assertFalse(predicate(device,SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame(device_id='87654321')})))
                    test.assertTrue(predicate(device,SimpleNamespace(manufacturer_data={MANUFACTURER_ID:frame()})))
                    return Device(address,'Synthetic',{'path':'/selected','props':{}})
            test=self
            modules={'dbus_fast':SimpleNamespace(BusType=SimpleNamespace(SYSTEM=1),Message=lambda **options:options,MessageType=SimpleNamespace(ERROR='error')),
                     'dbus_fast.aio':SimpleNamespace(MessageBus=Bus),'bleak.backends.device':SimpleNamespace(BLEDevice=Device),'bleak':SimpleNamespace(BleakScanner=Scanner)}
            with patch.dict('sys.modules',modules):result=asyncio.run(known_device(selected))
            self.assertEqual(result.address,address);self.assertIn('bus_closed',calls)
            self.assertEqual('scan' in calls,not cached)
            self.assertEqual(bool(result.details.get('bt06_fresh_discovery')),not cached)


if __name__=='__main__':unittest.main()
