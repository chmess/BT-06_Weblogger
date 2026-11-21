import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend.common.settings import DEFAULTS
from backend.server import Application, make_server


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


if __name__ == "__main__":
    unittest.main()
