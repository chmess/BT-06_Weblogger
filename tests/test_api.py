import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.common.settings import DEFAULTS
from backend.server import Application, make_server
from backend.common.bt06 import decode


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.app = Application(cls.root, "/klima", ["http://deskpi.test", "http://10.43.0.1"])
        cls.server = make_server(cls.app, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.origin = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, body=None, headers=None, method=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        final_headers = dict(headers or {})
        if body is not None:
            body = json.dumps(body)
            final_headers.setdefault("Content-Type", "application/json")
        connection.request(method or ("POST" if body is not None else "GET"), path, body=body, headers=final_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def auth(self):
        return {"Origin": self.origin, "X-CSRF-Token": self.app.csrf}

    def test_paths_assets_and_mime_types(self):
        for path, mime in (("/klima/", "text/html"), ("/klima/assets/favicon.svg", "image/svg+xml"),
                           ("/klima/favicon.ico", "image/x-icon"), ("/klima/js/app.js", "text/javascript"),
                           ("/klima/assets/echarts.min.js", "text/javascript")):
            status, headers, content = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(mime, headers["Content-Type"])
            self.assertTrue(content)
        self.assertEqual(self.request("/klima")[0], 308)
        for path in ("/", "/klima/../config/settings.json", "/klima/private/profiles.json", "/klima/%2e%2e/config/settings.json"):
            self.assertEqual(self.request(path)[0], 404)

    def test_csrf_origin_and_host_protection(self):
        self.assertEqual(self.request("/klima/api/settings", DEFAULTS)[0], 403)
        self.assertEqual(self.request("/klima/api/settings", DEFAULTS, {"Origin": "http://evil.example", "X-CSRF-Token": self.app.csrf})[0], 403)
        self.assertEqual(self.request("/klima/api/status", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("/klima/api/settings", DEFAULTS, self.auth())[0], 200)
        self.assertEqual(json.loads(self.request("/klima/api/settings")[2]), DEFAULTS)
        self.assertEqual(self.request("/klima/api/settings", {**DEFAULTS, "humidity_warning": 95}, self.auth())[0], 400)
        self.assertEqual(json.loads(self.request("/klima/api/settings")[2]), DEFAULTS)

    def test_generate_history_export_and_isolation(self):
        original = self.root / "data/real.csv"
        original.parent.mkdir(exist_ok=True)
        original.write_text("do not change")
        status, _, payload = self.request("/klima/api/simulation", {"days": 1, "interval_minutes": 5, "scenario": "gaps"}, self.auth())
        self.assertEqual(status, 201, payload)
        run = json.loads(payload)
        query = f"run={run['id']}&logger={run['loggers'][0]['id']}"
        status, _, history = self.request("/klima/api/history?" + query)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(history)["source"], "Simulation")
        status, headers, export = self.request("/klima/api/export?" + query)
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertTrue(export.startswith(b"\xef\xbb\xbfSchema;"))
        self.assertIn(b"Simulation", export)
        self.assertEqual(original.read_text(), "do not change")
        self.assertEqual(self.request("/klima/api/history?run=../real&logger=x")[0], 400)
        self.assertEqual(self.request("/klima/api/history?" + query + "&logger=duplicate")[0], 400)

    def test_busy_generation_rejected(self):
        self.app.generation_lock.acquire()
        try:
            self.assertEqual(self.request("/klima/api/simulation", {"days": 1}, self.auth())[0], 409)
        finally:
            self.app.generation_lock.release()

    def test_multiple_explicit_proxy_origins(self):
        for origin in ("http://deskpi.test", "http://10.43.0.1"):
            host = origin.removeprefix("http://")
            headers = {"Host": host, "Origin": origin, "X-CSRF-Token": self.app.csrf}
            self.assertEqual(self.request("/klima/api/status", headers={"Host": host})[0], 200)
            self.assertEqual(self.request("/klima/api/settings", DEFAULTS, headers)[0], 200)
        self.assertEqual(self.request("/klima/api/settings", DEFAULTS,
                                      {"Host": "deskpi.test", "Origin": "http://not-approved.test", "X-CSRF-Token": self.app.csrf})[0], 403)

    def test_real_source_export_is_separate_and_requires_known_logger(self):
        from datetime import datetime, timezone
        payload = bytearray(24)
        payload[:3] = bytes.fromhex("090205")
        payload[4:8] = bytes.fromhex("12345678")
        payload[11], payload[12] = 100, 2
        payload[15:19] = bytes.fromhex("c9002602")
        reading = decode(payload).json()
        self.app.live_store.append(reading, -55, datetime.now(timezone.utc).isoformat())
        status, _, body = self.request("/klima/api/history?source=live&logger=bt06-12345678")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["source"], "BLE-Advertising")
        self.assertEqual(json.loads(body)["raw_count"], 1)
        status, headers, body = self.request("/klima/api/export?source=live&logger=bt06-12345678")
        self.assertEqual(status, 200)
        self.assertIn(b"Batteriespannung", body)
        self.assertIn(b"Host-Empfang", body)
        self.assertNotIn(b"Simulation", body)
        self.assertEqual(self.request("/klima/api/history?source=live&run=x&logger=bt06-12345678")[0], 400)
        self.assertEqual(self.request("/klima/api/history?source=live&logger=bt06-87654321")[0], 400)
        self.assertEqual(self.request("/klima/api/history?source=unknown&logger=bt06-12345678")[0], 400)

    def test_capture_requires_explicit_verified_selection(self):
        self.assertEqual(self.request("/klima/api/live/start", {}, self.auth())[0], 400)
        self.assertEqual(self.request("/klima/api/live/start", {"device": "AA:BB:CC:DD:EE:FF"}, self.auth())[0], 400)
        self.app.bluetooth.candidates["AA:BB:CC:DD:EE:FF"] = "hci0"
        self.app.bluetooth.candidate_details["AA:BB:CC:DD:EE:FF"] = {"address": "AA:BB:CC:DD:EE:FF", "name": "Synthetic test logger", "bt06": {"device_id": "12345678", "firmware": "2.05"}}
        with patch.object(self.app.receiver, "start", return_value={"state": "starting"}) as start:
            status = self.request("/klima/api/live/start", {"device": "AA:BB:CC:DD:EE:FF", "adapter": "hci0", "save_interval_seconds": 60}, self.auth())[0]
            self.assertEqual(status, 202)
            self.assertEqual(start.call_args.args[0]["device"]["id"], "12345678")
        self.assertEqual(self.request("/klima/api/live/stop", {})[0], 403)


if __name__ == "__main__":
    unittest.main()
