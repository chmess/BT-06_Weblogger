"""Synthetic read-only capture shared by tests and disposable browser QA."""
from datetime import datetime, timedelta, timezone
from backend.common.bt06_gatt import ReadCommand, read_request


def u32(n):
    return n.to_bytes(4, 'little')


def packet(kind, body):
    return (len(body) + 1).to_bytes(2, 'little') + bytes([kind]) + body


def capture(seconds=None, values=None):
    if seconds is None:
        first = int(datetime(2024, 3, 31, 0, 30, tzinfo=timezone.utc).timestamp())
        seconds = [first, first + 600, first + 1200]
    values = values or [bytes.fromhex('c8005802')] * len(seconds)
    count = len(seconds)
    metadata = count.to_bytes(2, 'little') + u32(seconds[0]) + u32(seconds[-1])
    settings = (600).to_bytes(2, 'little') + bytes(13)
    rows = []
    def add(direction, data):
        stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=len(rows))
        rows.append({'Hostzeit': stamp.isoformat(), 'Richtung': direction, 'DatenHex': data.hex()})
    for command, payload in ((ReadCommand.LOG_STATUS, bytes(30)), (ReadCommand.SELECT_ALL_HISTORY, metadata),
                             (ReadCommand.LOG_SETTINGS, settings), (ReadCommand.RECEIVE_HISTORY, b'')):
        add('TX', read_request(command))
        add('RX', b'\x26' + command.value + b'\x01' + payload + b'\x23')
    add('RX', packet(0, u32(count)))
    for offset in range(0, count, 128):
        add('RX', packet(1, b''.join(u32(s) + value for s, value in zip(seconds[offset:offset+128], values[offset:offset+128]))))
    add('RX', packet(255, u32(count) + u32(1 + (count + 127) // 128)))
    return rows
