import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.common.history_capture import decode_capture
from backend.common.history_store import HistoryStore
from backend.common.history_timezones import HistoryTimezones,assigned_time
from history_fixture import capture


class HistoryTimezoneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.store=HistoryStore(root/'history');self.timezones=HistoryTimezones(root/'timezones.json',self.store)
        self.times=[1770000000+i*600 for i in range(3)]
        self.base=self.store.publish('12345678',**decode_capture(capture(self.times)))
    def tearDown(self):self.temp.cleanup()
    def assign(self):return self.timezones.assign({'logger':self.base['logger'],'snapshot':self.base['id'],'timezone':'Europe/Berlin','timezone_confirmed':True})

    def test_confirmed_offset_keeps_original_timestamp_empty_and_date_unverified(self):
        before=self.store.rows(self.base['logger'],self.base['id'])
        result=self.assign();self.assertTrue(result['timezone_confirmed']);self.assertFalse(result['clock_verified']);self.assertFalse(result['date_verified'])
        rows=list(self.timezones.export_rows(self.base['logger'],self.base['id']))
        self.assertEqual({row['Zeitstempel'] for row in rows},{''})
        self.assertTrue(all(row['ZugeordneteZeit'].endswith('+01:00') for row in rows))
        self.assertEqual(self.store.rows(self.base['logger'],self.base['id']),before)
        reloaded=HistoryTimezones(self.timezones.path,self.store)
        self.assertEqual(reloaded.info(self.base['logger'],self.base['id'])['assigned_count'],3)

    def test_later_records_are_not_implicitly_confirmed(self):
        self.assign()
        later=self.store.publish('12345678',**decode_capture(capture(self.times+[self.times[-1]+600])))
        info=self.timezones.info(later['logger'],later['id'])
        self.assertEqual(info['assigned_count'],3);self.assertEqual(info['unassigned_count'],1)
        rows=list(self.timezones.export_rows(later['logger'],later['id']))
        self.assertEqual(rows[-1]['ZugeordneteZeit'],'')
        self.assertEqual(rows[-1]['Zeitzuordnung'],'BEREICH_NICHT_BESTAETIGT')

    def test_different_raw_branch_is_not_assigned(self):
        self.assign();other=self.store.publish('12345678',**decode_capture(capture(self.times,[bytes.fromhex('c9005802')]*3)))
        self.assertFalse(self.timezones.info(other['logger'],other['id'])['timezone_confirmed'])
        with self.assertRaises(ValueError):list(self.timezones.export_rows(other['logger'],other['id']))

    def test_dst_ambiguous_and_missing_hours_are_rejected(self):
        berlin=ZoneInfo('Europe/Berlin')
        for calendar in ('2026-03-29T02:30:00','2026-10-25T02:30:00'):
            with self.assertRaises(ValueError):assigned_time(calendar,berlin)
        self.assertEqual(assigned_time('2026-03-10T12:00:00',berlin),'2026-03-10T12:00:00+01:00')
        self.assertEqual(assigned_time('2026-07-10T12:00:00',berlin),'2026-07-10T12:00:00+02:00')
        self.assertEqual(assigned_time('2026-03-10T12:00:00',ZoneInfo('UTC')),'2026-03-10T12:00:00+00:00')

    def test_explicit_confirmation_required(self):
        options={'logger':self.base['logger'],'snapshot':self.base['id'],'timezone':'Europe/Berlin','timezone_confirmed':False}
        with self.assertRaises(ValueError):self.timezones.assign(options)
        self.assertFalse(self.timezones.path.exists())
        with self.assertRaises(ValueError):self.timezones.assign({**options,'timezone_confirmed':True,'timezone':'Unknown/zone'})


if __name__=='__main__':unittest.main()
