"""Prepare complete CSV privately before committing download headers."""
import codecs
import csv
import shutil
import tempfile
from contextlib import contextmanager

MAX_BYTES=256*1024*1024
RESERVE_BYTES=64*1024*1024
CHUNK_BYTES=64*1024


class CsvBudgetError(ValueError):pass


class CsvSink:
    def __init__(self,stream,folder,maximum,reserve):
        self.stream=stream;self.folder=folder;self.reserve=reserve;self.size=0;self.next_check=0
        self.maximum=min(maximum,max(0,shutil.disk_usage(folder).free-reserve))
        self.write_bytes(codecs.BOM_UTF8)

    def write_bytes(self,data):
        size=self.size+len(data)
        if size>=self.next_check:
            available=shutil.disk_usage(self.folder).free-self.reserve-8192
            self.maximum=min(self.maximum,self.size+max(0,available))
            if available<len(data):raise CsvBudgetError('Zu wenig temporärer Speicher; Reserve für Messdaten bleibt geschützt.')
            self.next_check=size+1024*1024
        if size>self.maximum:raise CsvBudgetError('CSV überschreitet das Export-/Speicherbudget. Zeitraum oder Spalten eingrenzen.')
        if self.stream.write(data)!=len(data):raise OSError('CSV-Vorbereitung unvollständig.')
        self.size=size

    def write(self,text):
        self.write_bytes(text.encode('utf-8'));return len(text)


@contextmanager
def prepared_csv(rows,fields,folder,*,max_bytes=MAX_BYTES,reserve_bytes=RESERVE_BYTES):
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    iterator=iter(rows);closed=False
    def close_rows():
        nonlocal closed
        if not closed:
            closed=True
            if hasattr(iterator,'close'):iterator.close()
    try:
        with tempfile.TemporaryFile(mode='w+b',dir=folder,prefix='.csv-export-') as stream:
            try:
                sink=CsvSink(stream,folder,max_bytes,reserve_bytes)
                writer=csv.DictWriter(sink,fields,delimiter=';',lineterminator='\n');writer.writeheader();writer.writerows(iterator)
                stream.flush();size=stream.tell()
                if size!=sink.size:raise OSError('CSV-Vorbereitung unvollständig.')
            finally:
                close_rows()
            stream.seek(0)
            yield stream,size
    finally:
        close_rows()
