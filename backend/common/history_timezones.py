"""User-confirmed timezone interpretation; never repairs a device calendar."""
import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .settings import atomic_json
from .storage import identifier, parse_time

ASSIGNED_FIELDS = ['ZugeordneteZeit', 'BestaetigteZeitzone', 'Zeitzuordnung']


def assigned_time(calendar, zone):
    local = datetime.fromisoformat(calendar)
    if local.tzinfo is not None:
        raise ValueError('Gerätekalender darf keinen behaupteten UTC-Offset enthalten.')
    possibilities = {}
    for fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=fold)
        utc = candidate.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            possibilities[utc] = candidate
    if len(possibilities) != 1:
        raise ValueError('Gerätezeit liegt in einer mehrdeutigen oder nicht existierenden Stunde der Zeitumstellung. Keine automatische Zuordnung.')
    return next(iter(possibilities.values())).isoformat()


class HistoryTimezones:
    def __init__(self, path, store):
        self.path, self.store = path, store
        self.lock = threading.RLock()
        self.value = json.loads(path.read_text()) if path.exists() else {'schema_version': 1, 'assignments': {}}
        if not isinstance(self.value, dict) or set(self.value) != {'schema_version', 'assignments'} or self.value['schema_version'] != 1 or not isinstance(self.value['assignments'], dict):
            raise ValueError('Ungültige Historien-Zeitzuordnung; Originaldatei erhalten.')
        for logger, entry in self.value['assignments'].items():
            identifier(logger)
            if not isinstance(entry, dict) or set(entry) != {'snapshot', 'timezone', 'confirmed_at'}:
                raise ValueError('Ungültige bestätigte Zeitzone.')
            self.store._folder(logger, entry['snapshot'])
            self._zone(entry['timezone'])
            parse_time(entry['confirmed_at'])

    def _zone(self, name):
        try:
            if not isinstance(name, str):
                raise ValueError('Ungültige Zeitzone.')
            return ZoneInfo(name)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError('Unbekannte Zeitzone.') from None

    def assign(self, options):
        if (not isinstance(options, dict) or set(options) != {'logger', 'snapshot', 'timezone', 'timezone_confirmed'}
                or options['timezone_confirmed'] is not True):
            raise ValueError('Eine ausdrückliche Bestätigung der Zeitzone des gewählten Historienstands ist erforderlich.')
        zone = self._zone(options['timezone'])
        rows = self.store.rows(options['logger'], options['snapshot'])
        for row in rows:
            assigned_time(row['Geraetekalender'], zone)
        with self.lock:
            value = deepcopy(self.value)
            value['assignments'][options['logger']] = {'snapshot': options['snapshot'], 'timezone': options['timezone'],
                                                      'confirmed_at': datetime.now(timezone.utc).isoformat()}
            atomic_json(self.path, value)
            self.value = value
        return self.info(options['logger'], options['snapshot'])

    def _matched(self, logger, snapshot):
        with self.lock:
            entry = deepcopy(self.value['assignments'].get(logger))
        rows = self.store.rows(logger, snapshot)
        if not entry:
            return None, 0, rows
        selected_meta = self.store.metadata(logger, snapshot)
        base_meta = self.store.metadata(logger, entry['snapshot'])
        if (selected_meta['unit'], selected_meta['firmware']) != (base_meta['unit'], base_meta['firmware']):
            return None, 0, rows
        base = rows if entry['snapshot'] == snapshot else self.store.rows(logger, entry['snapshot'])
        limit = min(len(base), len(rows))
        signature = lambda row: (row['GeraeteSekunden'], row['RohwerteHex'])
        if [signature(row) for row in rows[:limit]] != [signature(row) for row in base[:limit]]:
            return None, 0, rows
        return entry, limit, rows

    def info(self, logger, snapshot):
        entry, count, rows = self._matched(logger, snapshot)
        return {'timezone': entry['timezone'] if entry else None, 'timezone_confirmed': entry is not None,
                'confirmed_at': entry['confirmed_at'] if entry else None, 'assigned_count': count,
                'unassigned_count': len(rows) - count, 'clock_verified': False,
                'date_verified': False, 'scope': 'timezone_only'}

    def export_rows(self, logger, snapshot, start=None, end=None):
        entry, limit, _ = self._matched(logger, snapshot)
        if entry is None:
            raise ValueError('Für diesen Historienstand ist keine passende Zeitzone bestätigt.')
        zone = self._zone(entry['timezone'])
        for row in self.store.filtered_rows(logger, snapshot, start, end):
            covered = int(row['Sequenz']) <= limit
            yield {**row, 'ZugeordneteZeit': assigned_time(row['Geraetekalender'], zone) if covered else '',
                   'BestaetigteZeitzone': entry['timezone'] if covered else '',
                   'Zeitzuordnung': 'ZEITZONE_BESTAETIGT_DATUM_UNGEPRUEFT' if covered else 'BEREICH_NICHT_BESTAETIGT'}
