"""Explicit BT06 2.05 history retrieval. No pairing, setters or logger start/stop."""
import asyncio
from datetime import datetime, timezone

from backend.common.bt06_gatt import SERVICE_UUID, TX_UUID, RX_UUID, ReadCommand, ProtocolError, read_request, read_reply
from backend.common.history_capture import decode_capture
from backend.common.history_protocol import HistoryDecoder


async def known_device(config):
    from bleak.backends.device import BLEDevice
    from dbus_fast.aio import MessageBus
    from dbus_fast import BusType, Message, MessageType
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await asyncio.wait_for(bus.call(Message(destination='org.bluez', path='/',
            interface='org.freedesktop.DBus.ObjectManager', member='GetManagedObjects')), 5)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('BlueZ-Inventar nicht verfügbar.')
        matches = []
        for path, interfaces in reply.body[0].items():
            props = interfaces.get('org.bluez.Device1', {})
            if (props.get('Address') and props['Address'].value.lower() == config['device']['address'].lower()
                    and props.get('Adapter') and props['Adapter'].value == '/org/bluez/' + config['adapter']):
                matches.append((path, props))
        if len(matches) > 1:
            raise RuntimeError('Gewählter Logger ist im BlueZ-Inventar nicht eindeutig.')
        if matches:
            path, props = matches[0]
            if props.get('Connected') and props['Connected'].value:
                raise RuntimeError('Logger ist bereits verbunden. Andere Verbindung zuerst trennen.')
            return BLEDevice(config['device']['address'], config['device']['name'],
                             {'path': path, 'props': {key: value.value for key, value in props.items()}})
    finally:
        bus.disconnect()
    # Unpaired BlueZ entries can disappear when host discovery stops. A missing
    # cache entry is not evidence that the chosen logger is unavailable.
    from bleak import BleakScanner
    from backend.common.bt06 import advertised_reading
    from .ble_options import scan_options
    def selected(device, advertisement):
        if device.address.lower() != config['device']['address'].lower():
            return False
        reading = advertised_reading(advertisement.manufacturer_data)
        return bool(reading and reading['device_id'] == config['device']['id']
                    and reading['firmware'] == config['device']['firmware'])
    target = await BleakScanner.find_device_by_filter(selected, timeout=35, bluez=scan_options(config['adapter']))
    if target is None:
        raise RuntimeError('Gewählter Logger mit bestätigtem Format während der Suche nicht gefunden.')
    target.details['bt06_fresh_discovery'] = True
    return target


async def retrieve(config, progress, base=None, automatic=False, *, client=None):
    if automatic and base is None:
        raise ProtocolError('Automatisches Nachladen benötigt eine eindeutige geprüfte Basis. Zuerst vollständig lesen.')
    owned = client is None
    if owned:
        from bleak import BleakClient
        target = await known_device(config)
        # Include a complete 30-second advertising interval for cached targets.
        connect_seconds = (8 if getattr(target, 'details', {}).get('bt06_fresh_discovery') else 35) if automatic else 45
        client = BleakClient(target, pair=False, timeout=connect_seconds)
    queue = asyncio.Queue(maxsize=1024)
    capture = []
    received_bytes = 0
    overflow = False

    def note(direction, raw):
        capture.append({'Hostzeit': datetime.now(timezone.utc).isoformat(), 'Richtung': direction, 'DatenHex': raw.hex()})

    def notify(sender, data):
        nonlocal received_bytes, overflow
        raw = bytes(data)
        received_bytes += len(raw)
        if received_bytes > 2_000_000 or len(capture) >= 50000 or queue.full():
            overflow = True
            return
        note('RX', raw)
        queue.put_nowait(raw)

    async def response():
        raw = await asyncio.wait_for(queue.get(), 20)
        if overflow:
            raise ProtocolError('Historien-Empfangslimit überschritten.')
        return raw

    async def command(operation, selection=None):
        raw = read_request(operation, selection=selection)
        note('TX', raw)
        await asyncio.wait_for(client.write_gatt_char(tx, raw, response=True), 8)
        return read_reply(operation, await response())

    try:
        if owned:
            progress('connecting')
            await asyncio.wait_for(client.connect(), connect_seconds + (1 if automatic else 5))
        service = client.services.get_service(SERVICE_UUID)
        tx = service.get_characteristic(TX_UUID) if service else None
        rx = service.get_characteristic(RX_UUID) if service else None
        if tx is None or rx is None or 'write' not in tx.properties or 'notify' not in rx.properties:
            raise ProtocolError('GATT-Service passt nicht zum verifizierten BT06-Format.')
        await asyncio.wait_for(client.start_notify(rx, notify), 8)
        progress('reading_metadata')
        await command(ReadCommand.DEVICE_CLOCK)
        await command(ReadCommand.LOG_STATUS)
        metadata = await command(ReadCommand.SELECT_ALL_HISTORY)
        settings = await command(ReadCommand.LOG_SETTINGS)
        if len(metadata) != 10 or len(settings) != 15 or settings[6] not in (0, 1):
            raise ProtocolError('Unbekanntes Historien-Metadatenformat.')
        count = int.from_bytes(metadata[:2], 'little')
        if not count:
            raise ProtocolError('Logger meldet keine gespeicherte Historie.')
        if base:
            first = int.from_bytes(metadata[2:6], 'little')
            last = int.from_bytes(metadata[6:10], 'little')
            unit = 'F' if settings[6] else 'C'
            if (count >= base['count'] and first == base['first'] and last >= base['last']
                    and last < 0xFFFFFFFF and unit == base['unit']
                    and int.from_bytes(settings[:2], 'little') == base['interval_seconds']):
                progress('selecting_range')
                selected = await command(ReadCommand.SELECT_ALL_HISTORY, (base['begin'], last + 1))
                if (len(selected) != 10 or int.from_bytes(selected[:2], 'little') != count - base['count'] + base['overlap']
                        or int.from_bytes(selected[2:6], 'little') < base['begin']
                        or int.from_bytes(selected[6:10], 'little') != last):
                    raise ProtocolError('Nachladebereich passt nicht zu den Gesamtmetadaten. Vollständig lesen.')
                metadata = selected
                count = int.from_bytes(metadata[:2], 'little')
            else:
                if automatic:
                    raise ProtocolError('Gesamtbestand oder Einstellungen geändert. Manuell vollständig lesen.')
                progress('full_fallback')
        decoder = HistoryDecoder(count, unit='F' if settings[6] else 'C')
        progress('receiving', expected=count, received=0)
        await command(ReadCommand.RECEIVE_HISTORY)
        while not decoder.ended:
            decoder.feed(await response())
            progress('receiving', expected=count, received=len(decoder.records))
        decoder.finish()
        if overflow or not queue.empty():
            raise ProtocolError('Unerwartete Daten nach Historienende.')
        await asyncio.wait_for(client.stop_notify(rx), 8)
        transfer = decode_capture(capture)
        if 'selection' in transfer:
            transfer['base_snapshot'] = base['snapshot']
        return transfer
    finally:
        if owned:
            await asyncio.wait_for(client.disconnect(), 10)
