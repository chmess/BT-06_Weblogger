import unittest

from backend.common.bt06_gatt import ProtocolError, ReadCommand, device_clock, read_reply, read_request


class ReadProtocolTests(unittest.TestCase):
    def test_device_clock_keeps_unverified_timezone_and_old_calendar(self):
        clock = device_clock(bytes([20, 2, 29, 23, 59, 58]), year_base=1980)
        self.assertEqual(clock.isoformat(), "2000-02-29T23:59:58")
        self.assertIsNone(clock.tzinfo)
        for invalid in (b"", bytes([21, 2, 29, 0, 0, 0]), bytes([46, 13, 1, 0, 0, 0]), bytes([46, 1, 1, 24, 0, 0])):
            with self.assertRaises(ProtocolError):
                device_clock(invalid, year_base=1980)
        with self.assertRaises(ProtocolError):
            device_clock(bytes([46, 1, 1, 0, 0, 0]), year_base=1900)

    def test_only_explicit_read_operations_can_be_encoded(self):
        self.assertEqual(read_request(ReadCommand.DEVICE_CLOCK), bytes.fromhex("2a03725123"))
        self.assertEqual(read_request(ReadCommand.LOG_STATUS), bytes.fromhex("2a034c0123"))
        for invalid in (b"\x4c\x02", "DEVICE_CLOCK", None):
            with self.assertRaises(TypeError):
                read_request(invalid)

    def test_success_and_empty_reply(self):
        self.assertEqual(read_reply(ReadCommand.LOG_STATUS, bytes.fromhex("264c010100ff23")), b"\x00\xff")
        self.assertEqual(read_reply(ReadCommand.DEVICE_INFO, bytes.fromhex("2672330123")), b"")

    def test_failed_wrong_truncated_and_invalid_replies_never_pass(self):
        for reply in (b"", b"\x26", bytes.fromhex("264c0101"),
                      bytes.fromhex("264c01012300"), bytes.fromhex("274c010123"),
                      bytes.fromhex("2672330123"), bytes.fromhex("264c010023"),
                      bytes.fromhex("264c010223")):
            with self.subTest(reply=reply.hex()), self.assertRaises(ProtocolError):
                read_reply(ReadCommand.LOG_STATUS, reply)


if __name__ == "__main__":
    unittest.main()
