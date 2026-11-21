"""Bounded BT06 2.05 history stream decoder; device seconds remain unzoned.

No radio access, no device configuration, no implicit host-time correction.
The end layout is verified on firmware 2.05, not assumed for other versions.
"""
from dataclasses import dataclass
from .bt06_gatt import ProtocolError


@dataclass(frozen=True)
class HistoryRecord:
    ordinal: int
    device_seconds: int
    temperature_c: float | None
    humidity_pct: float | None
    raw_values_hex: str


def _value(pair):
    if pair[1] == 0xFE:
        return None
    number = int.from_bytes(pair, "little")
    return (-1 if number & 0x8000 else 1) * (number & 0x7FFF) / 10


class HistoryDecoder:
    def __init__(self, expected_count, *, unit):
        if type(expected_count) is not int or not 0 <= expected_count <= 65535:
            raise ValueError("Ungültige erwartete Historienanzahl.")
        if unit not in ("C", "F"):
            raise ValueError("Historieneinheit nicht bestätigt.")
        self.expected_count, self.unit = expected_count, unit
        self.records = []
        self.pending = bytearray()
        self.frame_count = 0
        self.announced_count = None
        self.next_seconds = self.interval = None
        self.ended = False
        self.failed = False

    def feed(self, chunk):
        if self.failed:
            raise ProtocolError("Historienparser nach Fehler gesperrt.")
        try:
            self._feed(chunk)
        except (ValueError, TypeError, OverflowError):
            self.failed = True
            raise

    def _feed(self, chunk):
        if self.ended and chunk:
            raise ProtocolError("Daten nach Historienende.")
        if len(chunk) > 65536:
            raise ProtocolError("Historienblock zu groß.")
        self.pending.extend(chunk)
        while len(self.pending) >= 2:
            size = int.from_bytes(self.pending[:2], "little")
            if not 1 <= size <= 4096:
                raise ProtocolError("Ungültige Historienrahmenlänge.")
            if len(self.pending) < size + 2:
                break
            payload = bytes(self.pending[2:size + 2])
            del self.pending[:size + 2]
            self._packet(payload)
            self.frame_count += 1
            if self.ended and self.pending:
                raise ProtocolError("Überzählige Daten nach Historienende.")

    def _packet(self, payload):
        kind, body = payload[0], payload[1:]
        if kind == 0:
            if self.frame_count or len(body) != 4:
                raise ProtocolError("Fehlende/eingeschobene Historienanzahl.")
            self.announced_count = int.from_bytes(body, "little")
            if self.announced_count != self.expected_count:
                raise ProtocolError("Historienanzahl widerspricht Metadaten.")
            return
        if self.announced_count is None:
            raise ProtocolError("Historie ohne bestätigte Anzahl.")
        if kind == 255:
            if len(body) != 8 or int.from_bytes(body[:4], "little") != self.expected_count or int.from_bytes(body[4:], "little") != self.frame_count:
                raise ProtocolError("Historienendemarkierung widerspricht Übertragung.")
            if len(self.records) != self.expected_count:
                raise ProtocolError("Historienwerte fehlen.")
            self.ended = True
            return
        if kind == 3:
            if len(body) < 8:
                raise ProtocolError("Historienzeitkontext unvollständig.")
            self.next_seconds = int.from_bytes(body[:4], "little")
            self.interval = int.from_bytes(body[4:8], "little")
            if not self.interval:
                raise ProtocolError("Historienintervall ist null.")
            body, kind = body[8:], 2
        width = 8 if kind == 1 else 4 if kind == 2 else 0
        if not width or not body or len(body) % width:
            raise ProtocolError("Unbekannter/unvollständiger Historienblock.")
        for offset in range(0, len(body), width):
            sample = body[offset:offset + width]
            if kind == 1:
                seconds, values = int.from_bytes(sample[:4], "little"), sample[4:]
            else:
                if self.next_seconds is None or self.interval is None:
                    raise ProtocolError("Kompaktwerte ohne Zeitkontext.")
                seconds, values = self.next_seconds, sample
                self.next_seconds += self.interval
            if not 0 <= seconds <= 0xFFFFFFFF or len(self.records) >= self.expected_count:
                raise ProtocolError("Historienzeit/Anzahl außerhalb des Wertebereichs.")
            temperature, humidity = _value(values[:2]), _value(values[2:])
            if temperature is not None and self.unit == "F":
                temperature = (temperature - 32) * 5 / 9
            if temperature is not None and not -40 <= temperature <= 80:
                temperature = None
            if humidity is not None and not 0 <= humidity <= 100:
                humidity = None
            self.records.append(HistoryRecord(len(self.records) + 1, seconds, temperature, humidity, values.hex()))

    def finish(self):
        if self.failed or self.pending or not self.ended:
            raise ProtocolError("Historienübertragung nicht vollständig bestätigt.")
        return tuple(self.records)
