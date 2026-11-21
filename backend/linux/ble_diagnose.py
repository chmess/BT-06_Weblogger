"""Explicit, time-bounded BLE inventory. Pairing only with an explicit option."""
import argparse
import asyncio
import json
import sys
from backend.common.bt06 import advertised_reading


async def diagnose(args):
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError:
        raise RuntimeError("Bleak fehlt. Optional installieren: ./install.sh --ble (nur lokale .venv).") from None
    if args.command == "scan":
        devices = await BleakScanner.discover(timeout=args.seconds, return_adv=True, bluez={"adapter": args.adapter})
        return {"mode": "advertising-only", "seconds": args.seconds, "devices": [
            {"address": device.address, "name": advertisement.local_name or device.name,
             "rssi": advertisement.rssi, "service_uuids": advertisement.service_uuids,
             "manufacturer_data": {str(key): value.hex() for key, value in advertisement.manufacturer_data.items()},
             "service_data": {key: value.hex() for key, value in advertisement.service_data.items()},
             "bt06": advertised_reading(advertisement.manufacturer_data)}
            for device, advertisement in devices.values()]}
    # Connect as soon as the selected peripheral advertises, instead of waiting
    # for the full scan window. Slow-advertising loggers have short connect windows.
    target = await BleakScanner.find_device_by_address(args.device, timeout=args.seconds, bluez={"adapter": args.adapter})
    if not target:
        raise RuntimeError("Gewähltes Gerät während der Suche nicht gefunden.")
    async with BleakClient(target, timeout=30 if args.pair else 15, pair=args.pair, bluez={"adapter": args.adapter}) as client:
        services = []
        for service in client.services:
            services.append({"uuid": service.uuid, "characteristics": [
                {"uuid": characteristic.uuid, "properties": characteristic.properties,
                 "descriptors": [descriptor.uuid for descriptor in characteristic.descriptors]}
                for characteristic in service.characteristics]})
        return {"mode": "gatt-inventory-only", "address": target.address, "services": services,
                "pairing_requested": args.pair, "connected": False,
                "notice": "GATT-Inventar gelesen; Diagnoseverbindung anschließend geschlossen. Keine Characteristics gelesen, Notifications oder Logger-Konfigurationsbefehle."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "gatt"])
    parser.add_argument("--seconds", type=int, choices=range(1, 31), default=10)
    parser.add_argument("--adapter", default="hci0")
    parser.add_argument("--device", help="Explizite Geräteadresse für GATT-Inventar")
    parser.add_argument("--pair", action="store_true", help="Bei gatt ausdrücklich Betriebssystem-Kopplung versuchen (BlueZ-Agent ggf. erforderlich)")
    args = parser.parse_args()
    if args.command == "gatt" and not args.device:
        parser.error("gatt benötigt --device; kein automatisches Verbinden.")
    if args.command == "scan" and args.pair:
        parser.error("--pair ist nur mit gatt zulässig.")
    try:
        print(json.dumps(asyncio.run(asyncio.wait_for(diagnose(args), timeout=args.seconds + 45)), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"BLE-Diagnose fehlgeschlagen: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
