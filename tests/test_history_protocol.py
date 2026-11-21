import unittest
from backend.common.bt06_gatt import ProtocolError
from backend.common.history_protocol import HistoryDecoder


def u32(n):
    return n.to_bytes(4, "little")


def packet(kind, body):
    return (len(body) + 1).to_bytes(2, "little") + bytes([kind]) + body


def stream():
    # Synthetic data only: full record, time context + compact, continuation.
    return (packet(0, u32(3)) + packet(1, u32(1000) + bytes.fromhex("7b80f401"))
            + packet(3, u32(2000) + u32(60) + bytes.fromhex("c8005802"))
            + packet(2, bytes.fromhex("00fe00fe")) + packet(255, u32(3) + u32(4)))


class HistoryProtocolTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames_decode_identically(self):
        data = stream()
        for width in (1, 2, 7, 20, len(data)):
            decoder = HistoryDecoder(3, unit="C")
            for offset in range(0, len(data), width):
                decoder.feed(data[offset:offset + width])
            records = decoder.finish()
            self.assertEqual([r.device_seconds for r in records], [1000, 2000, 2060])
            self.assertEqual([r.temperature_c for r in records], [-12.3, 20, None])
            self.assertEqual([r.humidity_pct for r in records], [50, 60, None])
            self.assertEqual([r.ordinal for r in records], [1, 2, 3])

    def test_every_truncation_is_incomplete(self):
        data = stream()
        for size in range(len(data)):
            decoder = HistoryDecoder(3, unit="C")
            decoder.feed(data[:size])
            with self.assertRaises(ProtocolError):
                decoder.finish()

    def test_counts_context_unknown_frames_and_trailing_bytes_rejected(self):
        count = packet(0, u32(1))
        for invalid in (packet(0, u32(2)), count + count,
                        count + packet(2, bytes(4)), count + packet(42, b"x"),
                        count + packet(1, bytes(7)), count + packet(3, bytes(12)),
                        count + packet(255, u32(1) + u32(1)),
                        stream() + b"x", b"\x00\x00", b"\xff\xff"):
            decoder = HistoryDecoder(3 if invalid.startswith(stream()) else 1, unit="C")
            with self.subTest(data=invalid.hex()), self.assertRaises(ProtocolError):
                decoder.feed(invalid)
            with self.assertRaises(ProtocolError):
                decoder.finish()

    def test_end_frame_count_and_overflow_are_checked(self):
        data = stream()
        with self.assertRaises(ProtocolError):
            HistoryDecoder(3, unit="C").feed(data[:-4] + u32(99))
        decoder = HistoryDecoder(2, unit="C")
        with self.assertRaises(ProtocolError):
            decoder.feed(packet(0, u32(2)) + packet(3, u32(0xFFFFFFFF) + u32(60) + bytes(8)))

    def test_fahrenheit_and_repeated_times_preserve_record_identity(self):
        decoder = HistoryDecoder(2, unit="F")
        decoder.feed(packet(0, u32(2)) + packet(1, (u32(1000) + bytes.fromhex("a802f401")) * 2)
                     + packet(255, u32(2) + u32(2)))
        records = decoder.finish()
        self.assertAlmostEqual(records[0].temperature_c, 20)
        self.assertEqual(len(records), 2)


if __name__ == "__main__":
    unittest.main()
