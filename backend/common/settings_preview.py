"""Compare a local draft with verified settings. No BLE, persistence or approval."""
import unicodedata
from decimal import Decimal

from .device_settings import POWER_CODES


FIELDS = {
    'name': ('Gerätename', ''),
    'broadcast_interval_seconds': ('Sendeintervall', 's'),
    'transmit_power_dbm': ('Sendeleistung', 'dBm'),
    'record_interval_seconds': ('Aufzeichnungsintervall', 's'),
    'temperature_unit': ('Temperatureinheit', ''),
}


ALARM_FIELDS = {}
for alarm,label in (('temperature','Temperaturalarm'),('humidity','Feuchtealarm')):
    for bound,text in (('low','Untergrenze'),('high','Obergrenze')):
        for suffix,unit in (('limit','°C' if alarm=='temperature' else '% rF'),('enabled','')):
            key=f'{alarm}_alarm_{bound}_{suffix}'
            ALARM_FIELDS[key]=(alarm+'_alarm',bound,suffix)
            FIELDS[key]=(label+' '+text+(' aktiv' if suffix=='enabled' else ''),unit)


def editable_values(values):
    result=dict(values)
    for field,(alarm,bound,part) in ALARM_FIELDS.items():
        if part in values.get(alarm,{}).get(bound,{}):result[field]=values[alarm][bound][part]
    return result


def validate_value(field, value):
    if field in ALARM_FIELDS:
        alarm,bound,part=ALARM_FIELDS[field]
        if part=='enabled':
            if type(value) is not bool:raise ValueError('Alarmaktivierung muss wahr oder falsch sein.')
        else:
            low,high=(-20,60) if alarm=='temperature_alarm' else (0,100)
            if (type(value) not in (int,float) or not low<=value<=high
                    or Decimal(str(value))*10!=(Decimal(str(value))*10).to_integral_value()):
                raise ValueError('Alarmgrenze außerhalb des belegten Bereichs oder nicht in 0,1-Schritten.')
    elif field == 'name':
        if (not isinstance(value, str) or not value or value != value.strip()
                or any(unicodedata.category(c).startswith('C') for c in value)):
            raise ValueError('Gerätename: Text ohne Steuerzeichen oder äußere Leerzeichen erforderlich.')
        if len(value.encode('utf-8')) > 15:
            raise ValueError('Gerätename: höchstens 15 UTF-8-Bytes, keine automatische Kürzung.')
    elif field == 'transmit_power_dbm':
        if type(value) is not int or value not in POWER_CODES.values():
            raise ValueError('Sendeleistung: -20, -16, -12, -8, -4, 0, 4, 6 oder 8 dBm erforderlich.')
    elif field == 'broadcast_interval_seconds':
        if (type(value) not in (int, float) or not 0.5 <= value <= 30
                or Decimal(str(value)) * 10 != (Decimal(str(value)) * 10).to_integral_value()):
            raise ValueError('Sendeintervall: 0,5–30 Sekunden in exakten 0,1-Sekunden-Schritten erforderlich.')
    elif field == 'temperature_unit':
        if type(value) is not str or value not in ('C','F'):
            raise ValueError('Temperatureinheit: C oder F erforderlich.')
    elif field == 'record_interval_seconds':
        if type(value) is not int or not 10 <= value <= 64800:
            raise ValueError('Aufzeichnungsintervall: ganze Sekunden zwischen 10 und 64.800 erforderlich.')
    else:
        raise ValueError('Dieses Gerätefeld ist noch nicht zur Änderungsvorschau freigegeben.')
    return value


def validate_alarm_draft(current,desired):
    for alarm in ('temperature','humidity'):
        prefix=alarm+'_alarm_'
        if not any(key.startswith(prefix) for key in desired):continue
        if alarm=='temperature' and (current.get('temperature_unit')!='C' or desired.get('temperature_unit','C')!='C'):
            raise ValueError('Temperaturalarm vorerst nur bei unverändertem °C-Modus ändern.')
        target={}
        for field in ALARM_FIELDS:
            if not field.startswith(prefix):continue
            if field not in current:raise ValueError('Alarmblock zuerst vollständig auslesen.')
            validate_value(field,current[field]);target[field]=validate_value(field,desired.get(field,current[field]))
        if target[prefix+'low_limit']>=target[prefix+'high_limit']:
            raise ValueError('Alarmuntergrenze muss kleiner als Obergrenze sein.')


def settings_preview(config, saved, request):
    if not isinstance(request, dict) or set(request) != {'base_capture', 'changes'}:
        raise ValueError('Vorschau benötigt genau base_capture und changes.')
    device = config.get('device')
    if not device or device.get('firmware') != '2.05':
        raise ValueError('Zuerst einen verifizierten BT06 mit Firmware 2.05 auswählen.')
    if (not saved or saved.get('device_id') != device['id'] or saved.get('firmware') != device['firmware']
            or saved.get('capture') != request['base_capture']):
        raise ValueError('Einstellungsstand fehlt oder wurde ersetzt. Aktuellen Stand übernehmen und erneut prüfen.')
    desired = request['changes']
    if not isinstance(desired, dict) or not desired or set(desired) - set(FIELDS):
        raise ValueError('Nur Gerätename, Sendeintervall, Sendeleistung, Aufzeichnungsintervall Temperatureinheit und Alarmgrenzen sind als Vorschau verfügbar.')
    current = editable_values(saved['values'])
    changes = []
    for field in FIELDS:
        if field not in desired:
            continue
        value = validate_value(field, desired[field])
        if field not in current:
            raise ValueError(FIELDS[field][0] + ': bisheriger Wert nicht verifiziert; erneut auslesen.')
        validate_value(field, current[field])
        if current[field] != value:
            label, unit = FIELDS[field]
            changes.append({'field': field, 'label': label, 'before': current[field], 'after': value, 'unit': unit})
    alarm_changes=[item for item in changes if item['field'] in ALARM_FIELDS]
    if alarm_changes:
        validate_alarm_draft(current,{item['field']:item['after'] for item in changes})
    # These two values share one device parameter block. Never supply a
    # default for its unedited counterpart, even in a non-executable preview.
    broadcast = None
    if any(item['field'] in ('broadcast_interval_seconds', 'transmit_power_dbm') for item in changes):
        broadcast = {}
        for field in ('broadcast_interval_seconds', 'transmit_power_dbm'):
            if field not in current:
                raise ValueError('Funkparameter unvollständig. Intervall und Leistung zuerst gemeinsam auslesen.')
            validate_value(field, current[field])
            broadcast[field] = desired.get(field, current[field])
    logging = None
    if any(item['field'] in ('record_interval_seconds','temperature_unit') for item in changes):
        logging = {}
        for field in ('record_interval_seconds','temperature_unit'):
            if field not in current:
                raise ValueError('Aufzeichnungsparameter unvollständig. Intervall und Einheit zuerst gemeinsam auslesen.')
            validate_value(field,current[field])
            logging[field]=desired.get(field,current[field])
    return {
        'kind': 'device-settings-preview', 'device_id': device['id'], 'firmware': device['firmware'],
        'base_capture': saved['capture'], 'observed_at': saved['observed_at'],
        'changes': changes, 'broadcast_after': broadcast, 'logging_after': logging, 'write_available': False,
        'potential_history_loss': bool(changes), 'requires_full_history': bool(changes),
        'notice': ('Nur Vorschau. Speichern am BT06 kann die Gerätehistorie löschen. Es wurden keine Gerätebefehle gesendet.'
                   if changes else 'Keine Änderung gegenüber dem gelesenen Stand. Keine Gerätebefehle gesendet.'),
        'required_steps': ([
            'Gerät und Einstellungen unmittelbar vor dem Schreiben erneut prüfen.',
            'Gesamte aktuelle Historie vollständig lesen, prüfen und dauerhaft speichern; Nachladen allein reicht nicht.',
            'Aufzeichnungszustand und Folgen prüfen; konkrete Änderungen ausdrücklich bestätigen.',
            'Belegte Schreibbefehle ausführen und alle geänderten Werte am Gerät zurücklesen.',
        ] if changes else []),
        'write_block_reason': 'Schreibablauf noch nicht freigegeben; Vorschau ist keine Bestätigung und kein Vollständigkeitsnachweis.',
    }
