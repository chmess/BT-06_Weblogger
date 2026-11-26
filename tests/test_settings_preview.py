import copy
import tempfile
import unittest
from pathlib import Path

from backend.common.device_settings import DeviceSettingsStore
from backend.common.settings_preview import settings_preview
from settings_fixture import observation
from test_history_jobs import config


class SettingsPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DeviceSettingsStore(Path(self.temp.name) / 'settings')
        self.saved = self.store.save('12345678', observation())
        self.config = config()

    def preview(self, changes, **options):
        return settings_preview(self.config, self.saved,
                                {'base_capture': self.saved['capture'], 'changes': changes, **options})

    def test_diff_preserves_unedited_broadcast_counterpart_and_does_not_write(self):
        before = copy.deepcopy(self.saved)
        files = {p: p.read_bytes() for p in Path(self.temp.name).rglob('*') if p.is_file()}
        result = self.preview({'broadcast_interval_seconds': 0.5})
        self.assertEqual(result['changes'], [{'field': 'broadcast_interval_seconds', 'label': 'Sendeintervall',
                                              'before': 12.5, 'after': 0.5, 'unit': 's'}])
        self.assertEqual(result['broadcast_after'], {'broadcast_interval_seconds': 0.5, 'transmit_power_dbm': 0})
        self.assertFalse(result['write_available'])
        self.assertTrue(result['potential_history_loss'])
        self.assertTrue(result['requires_full_history'])
        self.assertEqual(self.saved, before)
        self.assertEqual(files, {p: p.read_bytes() for p in Path(self.temp.name).rglob('*') if p.is_file()})
        reverse = self.preview({'transmit_power_dbm': -20})
        self.assertEqual(reverse['broadcast_after']['broadcast_interval_seconds'], 12.5)

    def test_temperature_unit_requires_verified_interval_and_preserves_it(self):
        result=self.preview({'temperature_unit':'F'})
        self.assertEqual(result['logging_after'],{'temperature_unit':'F','record_interval_seconds':1230})
        self.assertEqual(result['changes'][0]['before'],'C')
        for value in ('K','f',1,True,None):
            with self.subTest(value=value),self.assertRaises(ValueError):self.preview({'temperature_unit':value})
        self.saved['values'].pop('record_interval_seconds')
        with self.assertRaises(ValueError):self.preview({'temperature_unit':'F'})

    def test_alarm_limits_activation_and_bounds_are_explicit(self):
        result=self.preview({'humidity_alarm_low_enabled':True,'humidity_alarm_high_limit':70.5})
        self.assertEqual(len(result['changes']),2)
        self.assertTrue(result['potential_history_loss'])
        for changes in ({'humidity_alarm_high_limit':101},{'humidity_alarm_high_limit':65.01},
                        {'humidity_alarm_high_limit':True},{'humidity_alarm_high_enabled':1},
                        {'humidity_alarm_low_limit':80},{'temperature_alarm_low_limit':-21},
                        {'temperature_alarm_high_limit':61},
                        {'temperature_alarm_high_limit':20,'temperature_unit':'F'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.preview(changes)
        self.saved['values']['temperature_unit']='F'
        with self.assertRaises(ValueError):self.preview({'temperature_alarm_high_limit':20})
        self.assertTrue(self.preview({'humidity_alarm_high_limit':70})['changes'])
        self.saved['values']['humidity_alarm'].pop('low')
        with self.assertRaises(ValueError):self.preview({'humidity_alarm_high_limit':70})

    def test_no_change_has_no_destructive_steps_or_write_permission(self):
        result = self.preview({'name': 'Demo BT06', 'broadcast_interval_seconds': 12.5, 'transmit_power_dbm': 0})
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['required_steps'], [])
        self.assertIsNone(result['broadcast_after'])
        self.assertFalse(result['potential_history_loss'])
        self.assertFalse(result['write_available'])

    def test_bad_types_limits_precision_and_unknown_parameters_are_rejected(self):
        cases = [{'name': x} for x in ('', ' space', 'space ', 'a\x00b', 'a\nb', 'a\u202eb', 'ä' * 8, 'x' * 16, True, 123)]
        cases += [{'broadcast_interval_seconds': x} for x in (True, '1', 0.4, 30.1, 1.01, 0.1 + 0.2, float('nan'), float('inf'), 10 ** 500)]
        cases += [{'transmit_power_dbm': x} for x in (True, 4.0, '4', 3, -21, 9)]
        cases += [{}, [], {'long_range': False}, {'transmit_rate_code': 0}, {'wire': '4335'}, {'name': 'valid', 'confirmed': True}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.preview(changes)
        for changes in ({'name': 'ä' * 7 + 'x'}, {'name': 'x' * 15}, {'broadcast_interval_seconds': 30},
                        {'broadcast_interval_seconds': 0.5}, {'broadcast_interval_seconds': 1.1}, {'transmit_power_dbm': 8}):
            self.assertTrue(self.preview(changes)['changes'])

    def test_replaced_capture_or_device_never_reuses_old_draft(self):
        old = self.saved['capture']
        self.saved = self.store.save('12345678', observation())
        with self.assertRaises(ValueError):
            settings_preview(self.config, self.saved, {'base_capture': old, 'changes': {'name': 'New name'}})
        for change in ({'id': '87654321'}, {'firmware': '2.06'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                changed = copy.deepcopy(self.config)
                changed['device'].update(change)
                settings_preview(changed, self.saved, {'base_capture': self.saved['capture'], 'changes': {'name': 'New name'}})
        with self.assertRaises(ValueError):
            settings_preview({'device': None}, self.saved, {'base_capture': old, 'changes': {'name': 'New name'}})
        with self.assertRaises(ValueError):
            self.preview({'name': 'New name'}, confirmed=True)

    def test_missing_or_invalid_counterpart_never_becomes_a_default(self):
        for value in (None, 99):
            saved = copy.deepcopy(self.saved)
            if value is None:
                saved['values'].pop('transmit_power_dbm')
            else:
                saved['values']['transmit_power_dbm'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings_preview(self.config, saved, {'base_capture': saved['capture'], 'changes': {'broadcast_interval_seconds': 1}})
        self.saved['values'].pop('name')
        with self.assertRaises(ValueError):
            self.preview({'name': 'New name'})


if __name__ == '__main__':
    unittest.main()
