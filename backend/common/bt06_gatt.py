"""Independently implemented BT06 command framing; read operations only.

Protocol facts verified against the manufacturer's BT06 SDK. A valid frame
alone does not establish that the selected firmware supports the operation.
No arbitrary opcode or configuration-writing interface is exposed here.
"""
from enum import Enum
from datetime import datetime


SERVICE_UUID = "6c400001-b5a3-f393-e0a9-e50e24dcca9e"
TX_UUID = "6c400002-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6c400003-b5a3-f393-e0a9-e50e24dcca9e"


class ReadCommand(Enum):
    DEVICE_INFO = b"\x72\x33"
    DEVICE_CLOCK = b"\x72\x51"
    LOG_STATUS = b"\x4c\x01"
    LOG_SETTINGS = b"\x72\x02"
    BROADCAST_SETTINGS = b"\x72\x35"
    TRANSMIT_RATE = b"\x72\x37"
    TEMPERATURE_ALARM = b"\x72\x20"
    HUMIDITY_ALARM = b"\x72\x23"
    SELECT_ALL_HISTORY = b"\x6c\x00"
    RECEIVE_HISTORY = b"\x6c\x01"


class ProtocolError(ValueError):
    pass


def read_request(command, *, selection=None):
    if not isinstance(command, ReadCommand):
        raise TypeError("Nur ausdrücklich unterstützte Leseabfragen zulässig.")
    payload = bytes(11) if command is ReadCommand.SELECT_ALL_HISTORY else b""
    if command in (ReadCommand.BROADCAST_SETTINGS, ReadCommand.TRANSMIT_RATE):
        payload = bytes(3)
    if selection is not None:
        if (command is not ReadCommand.SELECT_ALL_HISTORY or not isinstance(selection, tuple) or len(selection) != 2
                or any(type(value) is not int for value in selection) or not 0 < selection[0] < selection[1] <= 0xFFFFFFFF):
            raise ValueError("Ungültiger Historien-Lesebereich.")
        payload = b"\x02\x00\x00" + selection[0].to_bytes(4, "little") + selection[1].to_bytes(4, "little")
    return bytes([0x2a, 3 + len(payload)]) + command.value + payload + b"\x23"


def requested_range(data):
    """Recognize only the independently verified fixed time-range read frame."""
    data = bytes(data)
    if len(data) != 16 or data[:7] != b"\x2a\x0e\x6c\x00\x02\x00\x00" or data[-1] != 0x23:
        raise ProtocolError("Ungültige Historienbereichsabfrage.")
    selection = (int.from_bytes(data[7:11], "little"), int.from_bytes(data[11:15], "little"))
    if read_request(ReadCommand.SELECT_ALL_HISTORY, selection=selection) != data:
        raise ProtocolError("Ungültiger Historien-Lesebereich.")
    return selection


def read_reply(command, data):
    """Return payload only after envelope, command echo and success match.

    Each response must be supplied as one complete notification. Fragmented
    or unexpected replies are rejected; no attempt is made to guess/resync.
    The operation-specific payload still needs independent validation.
    """
    if not isinstance(command, ReadCommand):
        raise TypeError("Unbekannte Leseabfrage.")
    data = bytes(data)
    if len(data) < 5 or data[0] != 0x26 or data[-1] != 0x23:
        raise ProtocolError("Ungültiger BT06-Antwortrahmen.")
    if data[1:3] != command.value:
        raise ProtocolError("BT06-Antwort gehört zu einer anderen Abfrage.")
    if data[3] != 1:
        raise ProtocolError(f"BT06-Leseabfrage nicht erfolgreich (Status {data[3]}).")
    return data[4:-1]


def device_clock(payload, *, year_base):
    """Decode the six calendar fields without inventing a UTC offset.

    Year base must be explicitly established for the firmware: the older SDK
    says 1980, while real 2.05 metadata suggests 2000. There is no default.
    The result has no verified timezone and must not be used as a UTC stamp.
    """
    if type(year_base) is not int or year_base not in (1980, 2000):
        raise ProtocolError("Jahresbasis der Gerätefirmware nicht bestätigt.")
    if len(payload) != 6:
        raise ProtocolError("Ungültige Länge der BT06-Geräteuhr.")
    year, month, day, hour, minute, second = payload
    try:
        return datetime(year_base + year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ProtocolError("Ungültige Kalenderfelder der BT06-Geräteuhr.") from exc
