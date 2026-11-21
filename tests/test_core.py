import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from backend.common.settings import DEFAULTS, Settings, validate_settings
from backend.common.simulation import generate, list_runs, validate_options
from backend.common.storage import FIELDS, chart_data, csv_text, identifier, parse_time, rows_in_range
from backend.linux.runtime import InstanceLock


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_rejection_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            settings = Settings(path)
            self.assertFalse(path.exists())
            changed = {**DEFAULTS, "theme": "light"}
            settings.save(changed)
            original = path.read_bytes()
            for invalid in ({**changed, "humidity_warning": 90}, {**changed, "theme": "auto"},
                            {**changed, "timezone": "../etc/passwd"}, {**changed, "refresh_seconds": True},
                            {**changed, "humidity_warning": float("nan")}, {**changed, "secret": "x"}):
                with self.assertRaises(ValueError):
                    settings.save(invalid)
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(Settings(path).get(), changed)

    def test_failed_replace_preserves_previous_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            settings = Settings(path)
            settings.save(DEFAULTS)
            original = path.read_bytes()
            with patch("backend.common.settings.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    settings.save({**DEFAULTS, "theme": "light"})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(settings.get(), DEFAULTS)
            self.assertEqual(list(path.parent.glob(".pending-*")), [])

    def test_corrupt_config_never_silently_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text('{"broken":')
            with self.assertRaises(ValueError):
                Settings(path)
            self.assertEqual(path.read_text(), '{"broken":')


class SimulationTests(unittest.TestCase):
    def test_reproducible_csv_with_unique_runs_and_month_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            options = {"days": 2, "interval_minutes": 5, "seed": 7, "scenario": "humidity", "end": "2026-11-01T12:00:00+01:00"}
            first, second = generate(root, options), generate(root, options)
            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual(len(list_runs(root)), 2)
            for logger in first["loggers"]:
                rows = list(rows_in_range(root, first["id"], logger["id"]))
                self.assertEqual(rows, list(rows_in_range(root, second["id"], logger["id"])))
                self.assertEqual(len(rows), 577)
                self.assertEqual(len({r["DatensatzID"] for r in rows}), len(rows))
                self.assertEqual({r["Quelle"] for r in rows}, {"Simulation"})
                self.assertEqual({r["Batterie"] for r in rows}, {""})
                self.assertEqual({r["RSSI"] for r in rows}, {""})
                self.assertEqual(len(list((root / first["id"] / logger["id"]).glob("*/*.csv"))), 2)
                self.assertIn(",", rows[0]["Temperatur"])

    def test_dst_offsets_filter_exactly(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = generate(root, {"days": 2, "interval_minutes": 5, "scenario": "daily", "end": "2026-10-26T12:00:00+01:00"})
            logger = run["loggers"][0]["id"]
            # The repeated 02:00 hour refers to different UTC instants.
            summer = list(rows_in_range(root, run["id"], logger, "2026-10-25T02:00:00+02:00", "2026-10-25T02:00:00+02:00"))
            winter = list(rows_in_range(root, run["id"], logger, "2026-10-25T02:00:00+01:00", "2026-10-25T02:00:00+01:00"))
            self.assertEqual(len(summer), 1)
            self.assertEqual(len(winter), 1)
            self.assertNotEqual(summer[0]["DatensatzID"], winter[0]["DatensatzID"])
            with self.assertRaises(ValueError):
                list(rows_in_range(root, run["id"], logger, "2026-10-25T02:00:00", None))

    def test_failed_publication_is_not_listed_as_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Fail only the final directory publication, after writing a valid manifest.
            import os
            replace = os.replace
            def fail_directory(src, dst):
                if Path(src).is_dir():
                    raise OSError("interrupted publication")
                return replace(src, dst)
            with patch("backend.common.simulation.os.replace", side_effect=fail_directory):
                with self.assertRaises(OSError):
                    generate(root, {"days": 1})
            self.assertEqual(list_runs(root), [])

    def test_generation_limits_and_identifier_validation(self):
        for value in ({"days": 91}, {"days": 90, "interval_minutes": 1}, {"interval_minutes": 0}, {"days": True}, {"end": "2026-11-01T10:00:00"}):
            with self.assertRaises(ValueError):
                validate_options(value)
        for value in ("../real", "a/b", "", "/etc", "x\n"):
            with self.assertRaises(ValueError):
                identifier(value)

    def test_decimation_keeps_extrema_and_gaps_and_export_is_full(self):
        rows = []
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        for i in range(10000):
            if 3000 <= i < 3010:
                continue
            rows.append({"Schema": "1", "DatensatzID": str(i), "Zeitstempel": (start + timedelta(minutes=5 * i)).isoformat(),
                         "Temperatur": "-15,00" if i == 123 else "20,00", "Feuchte": "99,00" if i == 5678 else "60,00",
                         "Batterie": "", "RSSI": "", "Quelle": "Simulation", "Messstelle": "test", "Qualitaet": "SYNTHETISCH"})
        result = chart_data(iter(rows), 5)
        self.assertEqual(result["raw_count"], 9990)
        self.assertLess(len(result["points"]), 1650)
        self.assertEqual(min(p[1] for p in result["points"] if p[1] is not None), -15)
        self.assertEqual(max(p[2] for p in result["points"] if p[2] is not None), 99)
        self.assertTrue(any(p[1] is None for p in result["points"]))
        self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_text(rows)), delimiter=";"))), len(rows))

    def test_broken_csv_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = generate(root, {"days": 1, "end": "2026-11-21T00:00:00Z"})
            path = next((root / run["id"] / "demo-room").glob("*/*.csv"))
            with path.open("a") as stream:
                stream.write("1;incomplete\n")
            with self.assertRaises(ValueError):
                list(rows_in_range(root, run["id"], "demo-room"))

    def test_single_instance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lock"
            with InstanceLock(path):
                with self.assertRaises(RuntimeError):
                    with InstanceLock(path):
                        pass
            with InstanceLock(path):
                pass


if __name__ == "__main__":
    unittest.main()
