"""Fixed configuration frames derived independently from manufacturer facts.

Hardware side effects are not established by encoding or acknowledgement.
Only the guarded configuration workflow may send these frames.
"""
from decimal import Decimal

from .bt06_gatt import ProtocolError
from .device_settings import POWER_CODES,decode_settings
from .settings_preview import ALARM_FIELDS,editable_values,validate_alarm_draft,validate_value


STOP = bytes.fromhex('2a0352a123')
START = bytes.fromhex('2a0352a023')
SAVE = bytes.fromhex('2a0352a323')
FINISH = bytes.fromhex('2a0343ff23')


def configuration_frames(payloads, changes):
    """No access key, clock, radio-mode code, start, reset or arbitrary opcode."""
    frames = []
    if not changes or set(changes) - {'name', 'broadcast_interval_seconds', 'transmit_power_dbm', 'record_interval_seconds', 'temperature_unit'} - set(ALARM_FIELDS):
        raise ValueError('Keine unterstützten konkreten Geräteänderungen.')
    for key, value in changes.items():
        validate_value(key, value)
    if 'name' in changes:
        name = changes['name'].encode('utf-8').ljust(15, b'\xff')
        frames.append(b'\x2a\x12\x43\x33' + name + b'\x23')
    if {'broadcast_interval_seconds', 'transmit_power_dbm'} & set(changes):
        raw = payloads.get('broadcast_settings', b'')
        if len(raw) != 3 or raw[0] not in POWER_CODES:
            raise ProtocolError('Funkparameterblock nicht verifiziert.')
        interval = changes.get('broadcast_interval_seconds', int.from_bytes(raw[1:], 'little') / 10)
        power = changes.get('transmit_power_dbm', POWER_CODES[raw[0]])
        validate_value('broadcast_interval_seconds', interval); validate_value('transmit_power_dbm', power)
        code = next(key for key, value in POWER_CODES.items() if value == power)
        frames.append(b'\x2a\x06\x43\x35' + bytes([code]) + int(Decimal(str(interval))*10).to_bytes(2, 'little') + b'\x23')
    if {'record_interval_seconds','temperature_unit'} & set(changes):
        raw = payloads.get('log_settings', b'')
        if (len(raw) != 15 or raw[6] not in (0, 1) or not int.from_bytes(raw[:2], 'little')
                or any(value for index, value in enumerate(raw) if index not in (0, 1, 6))):
            raise ProtocolError('Unbekannte Aufzeichnungsfelder: Schreibauftrag blockiert, keine Null-Defaults.')
        updated = bytearray(raw)
        if 'record_interval_seconds' in changes:updated[:2]=changes['record_interval_seconds'].to_bytes(2,'little')
        if 'temperature_unit' in changes:updated[6]=int(changes['temperature_unit']=='F')
        updated=bytes(updated)
        frames.append(b'\x2a\x12\x43\x02' + updated + b'\x23')
    alarm_changes={key:value for key,value in changes.items() if key in ALARM_FIELDS}
    if alarm_changes:
        decoded=decode_settings(payloads)
        if any(key in decoded['decode_errors'] for key in ('temperature_alarm','humidity_alarm','log_settings')):
            raise ProtocolError('Alarmparameter nicht verifiziert.')
        validate_alarm_draft(editable_values(decoded['values']),{**alarm_changes,**({'temperature_unit':changes['temperature_unit']} if 'temperature_unit' in changes else {})})
        for alarm,opcode in (('temperature_alarm',b'\x43\x20'),('humidity_alarm',b'\x43\x23')):
            if not any(ALARM_FIELDS[key][0]==alarm for key in alarm_changes):continue
            raw=payloads.get(alarm,b'')
            if len(raw)!=12 or any(raw[i] not in (0,26) for i in (0,1,6,7)):
                raise ProtocolError('Alarmblock nicht verifiziert.')
            updated=bytearray(raw)
            for key,value in alarm_changes.items():
                block,bound,part=ALARM_FIELDS[key]
                if block!=alarm:continue
                offset=0 if bound=='low' else 6
                if part=='enabled':updated[offset]=26 if value else 0
                else:updated[offset+4:offset+6]=int(Decimal(str(value))*10).to_bytes(2,'little',signed=True)
            frames.append(b'\x2a\x0f'+opcode+bytes(updated)+b'#')
    return frames


def configuration_reply(frame, reply):
    reply = bytes(reply)
    if len(reply) != 5 or reply[:3] != b'\x26' + frame[2:4] or reply[3:] != b'\x01\x23':
        raise ProtocolError('Schreibantwort nicht eindeutig erfolgreich; keine automatische Wiederholung.')
