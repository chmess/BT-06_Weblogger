"""Independent decoder for the verified BT06 2.05 advertising layout.

Offsets/units are protocol facts inspected in the manufacturer's public SDK.
No manufacturer implementation or binary is distributed with this project.
"""
from dataclasses import asdict, dataclass

MANUFACTURER_ID = 0xFF23  # Bleak removes the on-air bytes 23 FF.
FORMAT = "bt06-2.05-advertising-v1"


@dataclass(frozen=True)
class Reading:
    device_id: str
    firmware: str
    temperature_c: float | None
    humidity_pct: float | None
    voltage_v: float
    recording: str
    memory_full: bool
    lock_level: int
    temperature_alarm: int
    humidity_alarm: int
    quality: str
    format: str = FORMAT

    def json(self):
        return asdict(self)


def decode(payload):
    """Decode only the verified firmware/layout; reject unknown variants."""
    if not isinstance(payload, (bytes, bytearray)) or len(payload) < 19:
        raise ValueError("Unvollständiges BT06-Advertising.")
    if payload[0] != 0x09:
        raise ValueError("Kein bestätigtes BT06-Format.")
    if payload[1:3] != b"\x02\x05":
        raise ValueError("Firmwareformat noch nicht verifiziert.")
    device_id = payload[4:8].hex()
    if not device_id.isdecimal():
        raise ValueError("Ungültige BT06-Gerätekennung.")
    unit = payload[14] & 3
    if unit == 2:
        raise ValueError("Unbekannte Temperatureinheit.")
    def numeric(pair):
        # Sign/magnitude, LE, tenths; FE in the high byte is a missing marker.
        if pair[1] == 0xFE:
            return None
        raw = int.from_bytes(pair, "little")
        return (-1 if raw & 0x8000 else 1) * (raw & 0x7FFF) / 10
    temperature = numeric(payload[15:17]) if unit != 3 else None
    humidity = numeric(payload[17:19]) if unit != 3 else None
    if temperature is not None and unit == 1:
        temperature = (temperature - 32) * 5 / 9
    if temperature is not None and not -40 <= temperature <= 80:
        temperature = None
    if humidity is not None and not 0 <= humidity <= 100:
        humidity = None
    quality = "OK" if temperature is not None and humidity is not None else "SENSOR_UNGUELTIG"
    return Reading(device_id, "2.05", round(temperature, 3) if temperature is not None else None,
                   humidity, (payload[11] + 200) / 100,
                   ("initialisiert", "Startverzoegerung", "zeichnet auf", "gestoppt")[payload[12] & 3],
                   bool(payload[12] & 4), (payload[12] >> 4) & 3,
                   payload[13] & 3, (payload[13] >> 2) & 3, quality)


def advertised_reading(manufacturer_data):
    data = manufacturer_data.get(MANUFACTURER_ID)
    if data is None:
        return None
    try:
        return decode(data).json()
    except ValueError:
        return None
