"""Atomic, immutable, content-addressed history snapshots; original data is CSV."""
import csv
import fcntl
import hashlib
import json
import os
import re
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .history_protocol import HistoryDecoder, history_record
from .storage import csv_text, decimal, identifier, parse_time

HISTORY_FIELDS = ['Schema', 'DatensatzID', 'Zeitstempel', 'Temperatur', 'Feuchte', 'Batterie', 'RSSI',
                  'Quelle', 'Messstelle', 'Qualitaet', 'GeraeteSekunden', 'Geraetekalender',
                  'Sequenz', 'RohwerteHex', 'Zeitbasis', 'Firmware']
CAPTURE_FIELDS = ['Hostzeit', 'Richtung', 'DatenHex']
SNAPSHOT_ID = re.compile(r'^[0-9a-f]{64}$')
OVERLAP = 16


def content_hash(unit):
    return hashlib.sha256(b'BT06-history-v1\x002.05\x00' + unit.encode())


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
        self._series_cache = None

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

    def publish(self, device_id, metadata, settings, chunks, capture, selection=None, full_metadata=None, base_snapshot=None):
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
        logger = 'bt06-' + device_id
        received_count = len(records)
        new_count = received_count
        if selection is not None:
            records, first, last, new_count = self._extend(logger, records, unit, selection, full_metadata, base_snapshot)
            count = len(records)
        elif base_snapshot is not None or full_metadata is not None:
            raise ValueError('Unerwartete Bereichsmetadaten beim Vollimport.')
        scope = 'range' if selection is not None else 'full'
        # Ordinal is a position within this full snapshot, not a stable device ID.
        digest = content_hash(unit)
        for record in records:
            digest.update(record.device_seconds.to_bytes(4, 'little') + bytes.fromhex(record.raw_values_hex))
        snapshot = digest.hexdigest()
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
                    'transfer_scope': scope, 'full_read_verified': scope == 'full',
                    'base_snapshot': base_snapshot, 'received_count': received_count, 'new_count': new_count,
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
                    return {**existing, 'duplicate': True, 'last_transfer_scope': scope,
                            'received_count': received_count, 'new_count': 0}
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
                return {**manifest, 'duplicate': False, 'last_transfer_scope': scope}

    def _extend(self, logger, selected, unit, selection, full_metadata, base_snapshot):
        if not base_snapshot or full_metadata is None or len(full_metadata) != 10:
            raise ValueError('Teilbereich benötigt einen geprüften Basisstand und aktuelle Gesamtmetadaten.')
        base_meta = self.metadata(logger, base_snapshot)
        previous = self.rows(logger, base_snapshot)
        if len(previous) < OVERLAP or base_meta['unit'] != unit:
            raise ValueError('Historienbasis für Nachladen ungeeignet. Vollständig lesen.')
        old = [history_record(i + 1, int(row['GeraeteSekunden']), bytes.fromhex(row['RohwerteHex']), unit)
               for i, row in enumerate(previous)]
        if any(b.device_seconds <= a.device_seconds for a, b in zip(old, old[1:])):
            raise ValueError('Uneindeutige Gerätezeit in der Basis. Vollständig lesen.')
        expected_count = int.from_bytes(full_metadata[:2], 'little')
        first, last = (int.from_bytes(full_metadata[i:i + 4], 'little') for i in (2, 6))
        if (tuple(selection) != (old[-OVERLAP].device_seconds - 1, last + 1)
                or first != old[0].device_seconds or last < old[-1].device_seconds
                or expected_count < len(old) or len(selected) != expected_count - len(old) + OVERLAP):
            raise ValueError('Historienbereich/Gesamtbestand hat sich geändert. Vollständig lesen.')
        signature = lambda item: (item.device_seconds, item.raw_values_hex)
        if [signature(item) for item in selected[:OVERLAP]] != [signature(item) for item in old[-OVERLAP:]]:
            raise ValueError('Überlappung stimmt nicht mit dem gespeicherten Bestand überein. Vollständig lesen.')
        if (selected[-1].device_seconds != last
                or any(b.device_seconds <= a.device_seconds for a, b in zip(selected, selected[1:]))):
            raise ValueError('Zeitverlauf des Nachladebereichs ist uneindeutig. Vollständig lesen.')
        added = [history_record(len(old) + i + 1, record.device_seconds, bytes.fromhex(record.raw_values_hex), unit)
                 for i, record in enumerate(selected[OVERLAP:])]
        return tuple(old + added), first, last, len(added)

    def series(self):
        """Collapse exact raw prefixes; divergent or shifted histories stay separate."""
        with self.lock:
            snapshots = self.snapshots()
            signature = []
            for meta in snapshots:
                folder = self._folder(meta['logger'], meta['id'])
                for name in ['manifest.json', *sorted(meta['files'])]:
                    stat = (folder / name).stat()
                    signature.append((meta['logger'], meta['id'], name, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
            if self._series_cache and self._series_cache[0] == signature:
                return deepcopy(self._series_cache[1])
            ancestors = {}
            for meta in snapshots:
                candidates = {item['id'] for item in snapshots if item['logger'] == meta['logger'] and item['unit'] == meta['unit']
                              and item['count'] < meta['count']}
                sizes = {item['count'] for item in snapshots if item['id'] in candidates}
                digest = content_hash(meta['unit'])
                prefixes = []
                for index, row in enumerate(self.rows(meta['logger'], meta['id']), 1):
                    digest.update(int(row['GeraeteSekunden']).to_bytes(4, 'little') + bytes.fromhex(row['RohwerteHex']))
                    if index in sizes and digest.hexdigest() in candidates:
                        prefixes.append(digest.hexdigest())
                if digest.hexdigest() != meta['id']:
                    raise ValueError('Historieninhalt widerspricht seiner Inhaltskennung.')
                ancestors[(meta['logger'], meta['id'])] = prefixes
            covered = {(logger, item) for (logger, _), items in ancestors.items() for item in items}
            heads = [{**meta, 'member_ids': ancestors[(meta['logger'], meta['id'])] + [meta['id']],
                      'member_count': len(ancestors[(meta['logger'], meta['id'])]) + 1}
                     for meta in snapshots if (meta['logger'], meta['id']) not in covered]
            for head in heads:
                head['separate_series'] = sum(other['logger'] == head['logger'] for other in heads)
            self._series_cache = (signature, deepcopy(heads))
            return heads

    def incremental_base(self, logger):
        heads = [head for head in self.series() if head['logger'] == logger]
        if len(heads) != 1 or heads[0]['count'] < OVERLAP or heads[0]['interval_seconds'] < 2:
            return None
        meta = heads[0]
        rows = self.rows(logger, meta['id'])
        seconds = [int(row['GeraeteSekunden']) for row in rows]
        if (seconds[0] == 0 or seconds[-1] >= 0xFFFFFFFF - 1
                or any(b <= a for a, b in zip(seconds, seconds[1:]))):
            return None
        return {'snapshot': meta['id'], 'count': len(rows), 'first': seconds[0], 'last': seconds[-1],
                'begin': seconds[-OVERLAP] - 1, 'overlap': OVERLAP, 'unit': meta['unit'],
                'interval_seconds': meta['interval_seconds']}

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
