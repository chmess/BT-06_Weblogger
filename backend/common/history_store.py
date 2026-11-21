"""Atomic, immutable, content-addressed history snapshots; original data is CSV."""
import csv
import fcntl
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .history_protocol import HistoryDecoder
from .storage import csv_text, decimal, identifier, parse_time

HISTORY_FIELDS = ['Schema', 'DatensatzID', 'Zeitstempel', 'Temperatur', 'Feuchte', 'Batterie', 'RSSI',
                  'Quelle', 'Messstelle', 'Qualitaet', 'GeraeteSekunden', 'Geraetekalender',
                  'Sequenz', 'RohwerteHex', 'Zeitbasis', 'Firmware']
CAPTURE_FIELDS = ['Hostzeit', 'Richtung', 'DatenHex']
SNAPSHOT_ID = re.compile(r'^[0-9a-f]{64}$')


def calendar(seconds):
    return (datetime(1970, 1, 1) + timedelta(seconds=seconds)).isoformat()


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_file(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


class HistoryStore:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()

    def _folder(self, logger, snapshot):
        identifier(logger)
        if not re.fullmatch(r'bt06-[0-9]{8}', logger) or not SNAPSHOT_ID.fullmatch(snapshot):
            raise ValueError('Ungültiger Historienstand.')
        return self.root / logger / snapshot

    def metadata(self, logger, snapshot):
        folder = self._folder(logger, snapshot)
        try:
            value = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        except FileNotFoundError:
            raise ValueError('Historienstand nicht gefunden.') from None
        if (value.get('schema_version') != 1 or value.get('id') != snapshot or value.get('logger') != logger
                or value.get('transport_complete') is not True or value.get('clock_verified') is not False):
            raise ValueError('Beschädigte Historienmetadaten; Originale erhalten.')
        files = value.get('files')
        if not isinstance(files, dict) or not files or any(not re.fullmatch(r'(?:[0-9]{4}/[0-9]{4}-[0-9]{2}|capture)\.csv', name) for name in files):
            raise ValueError('Ungültige Historien-Dateiliste.')
        return value

    def _verify(self, logger, snapshot):
        meta = self.metadata(logger, snapshot)
        folder = self._folder(logger, snapshot)
        for name, digest in meta['files'].items():
            if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
                raise ValueError('Historien-CSV beschädigt; Originale erhalten, Import gesperrt.')
        return meta

    def snapshots(self):
        with self.lock:
            if not self.root.exists():
                return []
            result = [self.metadata(path.parent.name, path.name) for path in self.root.glob('bt06-*/*')
                      if path.is_dir() and SNAPSHOT_ID.fullmatch(path.name)]
            return sorted(result, key=lambda item: (item['imported_at'], item['id']), reverse=True)

    def publish(self, device_id, metadata, settings, chunks, capture):
        """Verify transfer anew, then publish all CSV files in one directory rename."""
        if not isinstance(device_id, str) or not re.fullmatch(r'[0-9]{8}', device_id):
            raise ValueError('Ungültige BT06-Gerätekennung.')
        if len(metadata) != 10 or len(settings) != 15 or settings[6] not in (0, 1) or not int.from_bytes(settings[:2], 'little'):
            raise ValueError('Unbekanntes Historien-Metadatenformat.')
        count = int.from_bytes(metadata[:2], 'little')
        if not count:
            raise ValueError('Logger meldet eine leere Historie. Kein Import angelegt.')
        unit = 'F' if settings[6] else 'C'
        decoder = HistoryDecoder(count, unit=unit)
        for chunk in chunks:
            decoder.feed(chunk)
        records = decoder.finish()
        first, last = (int.from_bytes(metadata[i:i + 4], 'little') for i in (2, 6))
        if records[0].device_seconds != first or records[-1].device_seconds != last:
            raise ValueError('Historienanfang/-ende widersprechen Metadaten.')
        # Ordinal is a position within this full snapshot, not a stable device ID.
        digest = hashlib.sha256(b'BT06-history-v1\x002.05\x00' + unit.encode())
        for record in records:
            digest.update(record.device_seconds.to_bytes(4, 'little') + bytes.fromhex(record.raw_values_hex))
        snapshot = digest.hexdigest()
        logger = 'bt06-' + device_id
        grouped = {}
        for record in records:
            stamp = calendar(record.device_seconds)
            key = stamp[:4] + '/' + stamp[:7] + '.csv'
            grouped.setdefault(key, []).append({
                'Schema': '3', 'DatensatzID': f'{snapshot}-{record.ordinal}', 'Zeitstempel': '',
                'Temperatur': decimal(record.temperature_c) if record.temperature_c is not None else '',
                'Feuchte': decimal(record.humidity_pct) if record.humidity_pct is not None else '',
                'Batterie': '', 'RSSI': '', 'Quelle': 'BT06-Historie', 'Messstelle': logger,
                'Qualitaet': 'ZEIT_UNGEPRUEFT' if record.temperature_c is not None and record.humidity_pct is not None else 'ZEIT_UNGEPRUEFT_SENSOR_UNGUELTIG',
                'GeraeteSekunden': str(record.device_seconds), 'Geraetekalender': stamp,
                'Sequenz': str(record.ordinal), 'RohwerteHex': record.raw_values_hex,
                'Zeitbasis': 'Geraeteuhr-ohne-verifizierten-Offset', 'Firmware': '2.05'})
        capture_bytes = csv_text(capture, CAPTURE_FIELDS).encode('utf-8')
        files = {name: csv_text(rows, HISTORY_FIELDS).encode('utf-8') for name, rows in grouped.items()}
        files['capture.csv'] = capture_bytes
        monotonic = all(b.device_seconds >= a.device_seconds for a, b in zip(records, records[1:]))
        manifest = {'schema_version': 1, 'id': snapshot, 'logger': logger, 'firmware': '2.05',
                    'count': count, 'frame_count': decoder.frame_count, 'unit': unit,
                    'interval_seconds': int.from_bytes(settings[:2], 'little'),
                    'first_device_calendar': calendar(first), 'last_device_calendar': calendar(last),
                    'clock_verified': False, 'transport_complete': True, 'monotonic': monotonic,
                    'imported_at': datetime.now(timezone.utc).isoformat(),
                    'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        with self.lock:
            parent = self.root / logger
            parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (parent / '.import.lock').open('a+b') as guard:
                fcntl.flock(guard, fcntl.LOCK_EX)
                destination = self._folder(logger, snapshot)
                if destination.exists():
                    existing = self._verify(logger, snapshot)
                    for folder in (parent, self.root, self.root.parent):
                        sync_directory(folder)
                    return {**existing, 'duplicate': True}
                stage = parent / ('.pending-' + uuid.uuid4().hex)
                stage.mkdir(mode=0o700)
                # Failed stages remain unpublished. Retrying never relies on them.
                for name, data in files.items():
                    path = stage / name
                    path.parent.mkdir(exist_ok=True)
                    durable_file(path, data)
                durable_file(stage / 'manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
                for folder in {path.parent for path in stage.rglob('*.csv')}:
                    sync_directory(folder)
                sync_directory(stage)
                os.rename(stage, destination)
                for folder in (parent, self.root, self.root.parent):
                    sync_directory(folder)
                return {**manifest, 'duplicate': False}

    def rows(self, logger, snapshot):
        with self.lock:
            meta = self._verify(logger, snapshot)
            folder = self._folder(logger, snapshot)
            result = []
            for name in sorted(meta['files']):
                if name == 'capture.csv':
                    continue
                with (folder / name).open(encoding='utf-8', newline='') as stream:
                    reader = csv.DictReader(stream, delimiter=';')
                    if reader.fieldnames != HISTORY_FIELDS:
                        raise ValueError('Historien-CSV-Schemafehler.')
                    result.extend(reader)
            if len(result) != meta['count'] or any(None in row or any(v is None for v in row.values()) for row in result):
                raise ValueError('Unvollständige Historien-CSV.')
            result.sort(key=lambda row: int(row['Sequenz']))
            if [int(row['Sequenz']) for row in result] != list(range(1, meta['count'] + 1)):
                raise ValueError('Historiensequenz beschädigt.')
            return result

    def filtered_rows(self, logger, snapshot, start=None, end=None):
        # These UTC-shaped values are axis coordinates ONLY. API/UI must explicitly
        # label device calendar, never actual UTC or the user's configured timezone.
        first = parse_time(start).astimezone(timezone.utc) if start else None
        last = parse_time(end).astimezone(timezone.utc) if end else None
        if first and last and first > last:
            raise ValueError('Beginn liegt nach dem Ende.')
        for row in self.rows(logger, snapshot):
            axis = datetime.fromisoformat(row['Geraetekalender']).replace(tzinfo=timezone.utc)
            if (first is None or axis >= first) and (last is None or axis <= last):
                yield row

    def chart_rows(self, logger, snapshot, start=None, end=None):
        meta = self.metadata(logger, snapshot)
        if not meta['monotonic']:
            raise ValueError('Geräteuhr springt rückwärts. Original-CSV verfügbar; keine irreführende Verlaufslinie.')
        for row in self.filtered_rows(logger, snapshot, start, end):
            yield {**row, 'Zeitstempel': row['Geraetekalender'] + '+00:00'}
