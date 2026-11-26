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

    def test_climate_calculator_is_read_only_validated_and_session_protected(self):
        value={'temperature_c':20,'humidity_pct':50,'surface_temperature_c':10}
        self.assertEqual(self.request('/klima/api/climate/calculate',value)[0],403)
        status,_,raw=self.request('/klima/api/climate/calculate',value,headers=self.auth())
        self.assertEqual(status,200);result=json.loads(raw)
        self.assertAlmostEqual(result['dew_point_c'],9.26,delta=0.02)
        self.assertFalse(result['condensation_possible'])
        for invalid in ({**value,'humidity_pct':101},{**value,'surface_temperature_c':True},{**value,'unknown':True}):
            self.assertEqual(self.request('/klima/api/climate/calculate',invalid,headers=self.auth())[0],400)

    def test_auto_sync_settings_are_opt_in_and_protected(self):
        auto = json.loads(self.request('/klima/api/autosync')[2])
        self.assertFalse(auto['config']['enabled'])
        value = {'enabled': False, 'interval_minutes': 30}
        self.assertEqual(self.request('/klima/api/autosync', value)[0], 403)
        self.assertEqual(self.request('/klima/api/autosync', value, self.auth())[0], 200)
        self.assertEqual(self.request('/klima/api/autosync', {'enabled': True, 'interval_minutes': 30}, self.auth())[0], 400)
        self.assertFalse(json.loads(self.request('/klima/api/autosync')[2])['config']['enabled'])
        from test_history_jobs import config
        with patch.object(self.app.receiver, 'status', return_value={'config': config()}):
            enabled = {'enabled': True, 'interval_minutes': 30}
            status, _, body = self.request('/klima/api/autosync', enabled, self.auth())
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body)['config']['target']['id'], '12345678')
            with patch.object(self.app.sync, 'busy', return_value=True):
                self.assertEqual(self.request('/klima/api/autosync', value, self.auth())[0], 200)
        self.assertFalse(json.loads(self.request('/klima/api/autosync')[2])['config']['enabled'])

    def test_time_assignment_export_is_explicit_and_preserves_originals(self):
        from backend.common.history_capture import decode_capture
        from history_fixture import capture
        snapshot = self.app.history_store.publish('34567890', **decode_capture(capture()))
        query = f"source=device&logger={snapshot['logger']}&snapshot={snapshot['id']}"
        original = self.request('/klima/api/export?' + query)[2]
        self.assertEqual(self.request('/klima/api/export?' + query + '&time_basis=assigned')[0], 400)
        options = {'logger': snapshot['logger'], 'snapshot': snapshot['id'], 'timezone': 'Europe/Berlin', 'timezone_confirmed': True}
        self.assertEqual(self.request('/klima/api/time-assignment', options)[0], 403)
        status, _, payload = self.request('/klima/api/time-assignment', options, self.auth())
        self.assertEqual(status, 200, payload)
        self.assertFalse(json.loads(payload)['date_verified'])
        status, _, mapped = self.request('/klima/api/export?' + query + '&time_basis=assigned')
        self.assertEqual(status, 200, mapped)
        self.assertIn(b'ZugeordneteZeit', mapped)
        self.assertIn(b'+01:00', mapped)
        self.assertIn(b'ZEITZONE_BESTAETIGT_DATUM_UNGEPRUEFT', mapped)
        self.assertEqual(self.request('/klima/api/export?' + query)[2], original)
        self.assertEqual(self.request('/klima/api/history?' + query + '&time_basis=assigned')[0], 400)

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

    def test_device_settings_are_read_only_explicit_and_share_radio_lock(self):
        from settings_fixture import observation
        from test_history_jobs import config
        self.assertEqual(self.request('/klima/api/device-settings/read', {})[0], 403)
        self.assertEqual(self.request('/klima/api/device-settings/read', {}, self.auth())[0], 400)
        saved = self.app.device_settings.save('45678901', observation())
        selected = config();selected['device']['id'] = '45678901'
        with patch.object(self.app.receiver, 'status', return_value={'config': selected}), patch('backend.linux.settings_reader.known_device') as radio:
            status, _, body = self.request('/klima/api/device-settings')
            self.assertEqual(status, 200)
            value = json.loads(body)
            self.assertTrue(value['read_only'])
            self.assertEqual(value['settings']['values']['record_interval_seconds'], 1230)
            radio.assert_not_called()
            with patch.object(self.app.sync, 'busy', return_value=True):
                self.assertEqual(self.request('/klima/api/device-settings/read', {}, self.auth())[0], 409)
            with patch.object(self.app.sync, 'start', return_value={'state': 'running'}) as start:
                self.assertEqual(self.request('/klima/api/device-settings/read', {}, self.auth())[0], 202)
                self.assertEqual(start.call_args.args[0], {'mode': 'settings'})
        self.assertEqual(self.request('/klima/api/device-settings/write', {}, self.auth())[0], 404)

    def test_settings_preview_requires_current_selected_capture_and_never_starts_bluetooth(self):
        from settings_fixture import observation
        from test_history_jobs import config
        saved = self.app.device_settings.save('56789012', observation())
        selected = config(); selected['device']['id'] = '56789012'
        value = {'base_capture': saved['capture'], 'changes': {'broadcast_interval_seconds': 1}}
        self.assertEqual(self.request('/klima/api/device-settings/preview', value)[0], 403)
        with patch.object(self.app.receiver, 'status', return_value={'config': selected}), patch.object(self.app.sync, 'start') as start, patch.object(self.app.receiver, 'stop') as stop:
            status, _, body = self.request('/klima/api/device-settings/preview', value, self.auth())
            self.assertEqual(status, 200, body)
            result = json.loads(body)
            self.assertFalse(result['write_available'])
            self.assertEqual(result['changes'][0]['after'], 1)
            start.assert_not_called(); stop.assert_not_called()
            self.assertEqual(self.app.device_settings.latest('56789012'), saved)
            with patch.object(self.app.sync, 'busy', return_value=True):
                self.assertEqual(self.request('/klima/api/device-settings/preview', value, self.auth())[0], 409)
            self.app.device_settings.save('56789012', observation())
            self.assertEqual(self.request('/klima/api/device-settings/preview', value, self.auth())[0], 400)
            selected['device']['id'] = '87654321'
            self.assertEqual(self.request('/klima/api/device-settings/preview', value, self.auth())[0], 400)
        for route in ('write', 'save'):
            self.assertEqual(self.request('/klima/api/device-settings/' + route, value, self.auth())[0], 404)

    def test_configuration_endpoints_require_explicit_preparation_confirmation_and_shared_lock(self):
        status, _, body = self.request('/klima/api/device-settings/configuration')
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)['prepared'])
        self.assertFalse(json.loads(body)['reset_available'])
        for route in ('prepare', 'apply', 'cancel', 'verify'):
            path = '/klima/api/device-settings/' + route
            self.assertEqual(self.request(path, {})[0], 403)
            with patch.object(self.app.sync, 'busy', return_value=True):
                self.assertEqual(self.request(path, {}, self.auth())[0], 409)
        self.assertEqual(self.request('/klima/api/device-settings/prepare', {}, self.auth())[0], 400)
        self.assertEqual(self.request('/klima/api/device-settings/apply', {'token':'invented','confirm_history_loss':True,'confirm_stop':True}, self.auth())[0], 400)
        self.assertEqual(self.request('/klima/api/device-settings/cancel', {}, self.auth())[0], 200)
        self.assertEqual(self.request('/klima/api/device-settings/verify', {}, self.auth())[0], 400)
        self.assertEqual(self.request('/klima/api/device-settings/verify', {'confirmed':True}, self.auth())[0], 400)
        for mode in ('configuration_prepare', 'configuration_write', 'configuration_verify'):
            self.assertEqual(self.request('/klima/api/sync', {'mode':mode}, self.auth())[0], 400)

    def test_recording_routes_are_protected_and_cannot_be_started_through_sync(self):
        status,_,body=self.request('/klima/api/recording')
        self.assertEqual(status,200);self.assertIsNone(json.loads(body)['prepared'])
        for action in ('prepare','start','verify','cancel'):
            path='/klima/api/recording/'+action
            self.assertEqual(self.request(path,{})[0],403)
            with patch.object(self.app.sync,'busy',return_value=True):
                self.assertEqual(self.request(path,{},self.auth())[0],409)
            self.assertEqual(self.request(path,{},self.auth())[0],200 if action=='cancel' else 400)
        for mode in ('recording_prepare','recording_start','recording_verify'):
            self.assertEqual(self.request('/klima/api/sync',{'mode':mode},self.auth())[0],400)

    def test_device_history_chart_export_and_snapshot_access(self):
        from backend.common.history_capture import decode_capture
        from history_fixture import capture
        result = self.app.history_store.publish('23456789', **decode_capture(capture()))
        query = f"source=device&logger={result['logger']}&snapshot={result['id']}"
        status, _, body = self.request('/klima/api/history?' + query)
        self.assertEqual(status, 200, body)
        chart = json.loads(body)
        self.assertFalse(chart['clock_verified'])
        self.assertEqual(chart['axis_basis'], 'device_calendar')
        self.assertEqual(chart['raw_count'], 3)
        status, headers, body = self.request('/klima/api/export?' + query)
        self.assertEqual(status, 200)
        self.assertIn(b'Geraetekalender', body)
        self.assertIn(b'ZEIT_UNGEPRUEFT', body)
        self.assertNotIn(b'Host-Empfang', body)
        self.assertEqual(len(json.loads(self.request('/klima/api/snapshots')[2])['snapshots']), 1)
        for invalid in (query+'&run=x', 'source=device&logger=bt06-23456789&snapshot=missing',
                        'source=live&logger=bt06-12345678&snapshot=x'):
            self.assertEqual(self.request('/klima/api/history?'+invalid)[0], 400)
        self.assertEqual(self.request('/klima/api/sync', {})[0], 403)
        self.assertEqual(self.request('/klima/api/sync', {}, self.auth())[0], 400)
        first_series = json.loads(self.request('/klima/api/series')[2])['series']
        self.assertEqual(len(first_series), 1)
        self.assertEqual(first_series[0]['count'], 3)
        original = decode_capture(capture())
        begin = int.from_bytes(original['metadata'][2:6], 'little')
        extended = self.app.history_store.publish('23456789', **decode_capture(capture(seconds=[begin + i * 600 for i in range(4)])))
        series = json.loads(self.request('/klima/api/series')[2])['series']
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]['id'], extended['id'])
        self.assertEqual(series[0]['member_count'], 2)
        self.assertEqual(len(json.loads(self.request('/klima/api/snapshots')[2])['snapshots']), 2)

    def test_history_job_locks_radio_controls_but_leaves_reads_available(self):
        with patch.object(self.app.sync, 'busy', return_value=True):
            for route in ('sync','ble','live/start','live/stop'):
                self.assertEqual(self.request('/klima/api/'+route, {}, self.auth())[0], 409)
            for route in ('sync','snapshots','series','status','live'):
                self.assertEqual(self.request('/klima/api/'+route)[0], 200)

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
