import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from backend.common.csv_download import prepared_csv,CsvBudgetError
from backend.common.storage import csv_text


class Rows:
    def __init__(self,values):self.values=iter(values);self.closed=0
    def __iter__(self):return self
    def __next__(self):return next(self.values)
    def close(self):self.closed+=1


class CsvDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)/'runtime'

    def test_exact_bytes_bom_length_and_private_temporary_file(self):
        values=[{'Text':'Grüße; "Test"\nzweite Zeile'},{'Text':''}];rows=Rows(values)
        with prepared_csv(rows,['Text'],self.folder) as (stream,size):
            body=stream.read();self.assertEqual(body,csv_text(values,['Text']).encode('utf-8-sig'));self.assertEqual(len(body),size)
            self.assertEqual(os.fstat(stream.fileno()).st_mode&0o777,0o600);self.assertEqual(rows.closed,1)
        self.assertTrue(stream.closed);self.assertEqual(rows.closed,1);self.assertEqual(list(self.folder.iterdir()),[])

    def test_failed_preparation_closes_iterator_and_removes_temporary_data(self):
        rows=Rows([{'Wrong':'field'}])
        with self.assertRaises(ValueError):
            with prepared_csv(rows,['Text'],self.folder):self.fail('must not yield partial CSV')
        self.assertEqual(rows.closed,1);self.assertEqual(list(self.folder.iterdir()),[])
        with patch('backend.common.csv_download.CsvSink.write_bytes',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                with prepared_csv(Rows([]),['Text'],self.folder):self.fail('must not yield')
        self.assertEqual(list(self.folder.iterdir()),[])

    def test_size_and_disk_reserve_fail_before_yield(self):
        with self.assertRaises(CsvBudgetError):
            with prepared_csv(Rows([{'Text':'too large'}]),['Text'],self.folder,max_bytes=8):self.fail('must not yield')
        with patch('backend.common.csv_download.shutil.disk_usage',return_value=SimpleNamespace(free=100)):
            with self.assertRaises(CsvBudgetError):
                with prepared_csv(Rows([]),['Text'],self.folder,reserve_bytes=99):self.fail('must not yield')
        self.assertEqual(list(self.folder.iterdir()),[])

    def test_consumer_failure_cleans_up_without_reopening_source(self):
        rows=Rows([{'Text':'value'}])
        with self.assertRaises(OSError):
            with prepared_csv(rows,['Text'],self.folder) as (stream,size):raise OSError('consumer disconnected')
        self.assertTrue(stream.closed);self.assertEqual(rows.closed,1);self.assertEqual(list(self.folder.iterdir()),[])
