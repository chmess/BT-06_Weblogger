"""Replay bounded CSV captures of the verified read-only history sequence."""
import csv
from .bt06_gatt import ReadCommand, ProtocolError, read_reply, read_request, requested_range
from .history_store import CAPTURE_FIELDS
from .storage import parse_time


def decode_capture(rows):
    capture, chunks, replies = [], [], {}
    expected = None
    receiving = False
    selection = pending_range = full_metadata = None
    size = 0
    requests = {read_request(command): command for command in ReadCommand}
    for row in rows:
        if set(row) != set(CAPTURE_FIELDS) or any(not isinstance(v, str) for v in row.values()):
            raise ValueError('Ungültiges Historien-Capture-CSV.')
        parse_time(row['Hostzeit'])
        if len(row['DatenHex']) > 8192:
            raise ValueError('Historien-Capture-Block zu groß.')
        raw = bytes.fromhex(row['DatenHex'])
        size += len(raw)
        if size > 2_000_000 or len(capture) >= 50000:
            raise ValueError('Historien-Capture-Limit überschritten.')
        capture.append(dict(row))
        if row['Richtung'] == 'TX':
            if expected is not None or receiving:
                raise ProtocolError('Unbekannte oder überlappende Historienabfrage im Capture.')
            if raw in requests:
                expected = requests[raw]
                pending_range = None
            else:
                pending_range = requested_range(raw)
                expected = ReadCommand.SELECT_ALL_HISTORY
            if expected is ReadCommand.RECEIVE_HISTORY and not all(key in replies for key in (ReadCommand.SELECT_ALL_HISTORY, ReadCommand.LOG_SETTINGS)):
                raise ProtocolError('Historientransfer ohne Metadaten.')
        elif row['Richtung'] == 'RX':
            if receiving:
                chunks.append(raw)
            elif expected is not None:
                replies[expected] = read_reply(expected, raw)
                if expected is ReadCommand.SELECT_ALL_HISTORY:
                    selection = pending_range
                    if selection is None:
                        full_metadata = replies[expected]
                receiving = expected is ReadCommand.RECEIVE_HISTORY
                expected = None
            else:
                raise ProtocolError('Unerwartete Historienantwort im Capture.')
        else:
            raise ValueError('Ungültige Capture-Richtung.')
    if expected is not None or not receiving or not chunks:
        raise ProtocolError('Historien-Capture unvollständig.')
    result = {'metadata': replies[ReadCommand.SELECT_ALL_HISTORY],
              'settings': replies[ReadCommand.LOG_SETTINGS], 'chunks': chunks, 'capture': capture}
    if selection is not None:
        result.update(selection=selection, full_metadata=full_metadata)
    return result


def read_capture(path):
    if path.stat().st_size > 8_000_000:
        raise ValueError('Historien-Capture-Datei zu groß.')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter=';')
        if reader.fieldnames != CAPTURE_FIELDS:
            raise ValueError('Unbekanntes Historien-Capture-Schema.')
        return decode_capture(reader)
