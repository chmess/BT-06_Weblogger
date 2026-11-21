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
        if len(matches) != 1:
            raise RuntimeError('Gewählten Logger zuerst auf diesem Adapter suchen und Liveempfang einrichten.')
        path, props = matches[0]
        if props.get('Connected') and props['Connected'].value:
            raise RuntimeError('Logger ist bereits verbunden. Andere Verbindung zuerst trennen.')
        return BLEDevice(config['device']['address'], config['device']['name'],
                         {'path': path, 'props': {key: value.value for key, value in props.items()}})
    finally:
        bus.disconnect()


async def retrieve(config, progress):
    from bleak import BleakClient
    target = await known_device(config)
    client = BleakClient(target, pair=False, timeout=45)
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

    async def command(operation):
        raw = read_request(operation)
        note('TX', raw)
        await asyncio.wait_for(client.write_gatt_char(tx, raw, response=True), 8)
        return read_reply(operation, await response())

    try:
        progress('connecting')
        await asyncio.wait_for(client.connect(), 50)
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
        return decode_capture(capture)
    finally:
        await asyncio.wait_for(client.disconnect(), 10)
