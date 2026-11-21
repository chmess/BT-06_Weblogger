#!/usr/bin/env python3
"""Bounded synthetic workload, writes no production or device data."""
import json
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.common.simulation import generate
from backend.common.storage import chart_data, csv_text, rows_in_range


with tempfile.TemporaryDirectory(prefix="bt06-benchmark-") as folder:
    root = Path(folder)
    started = time.perf_counter()
    run = generate(root, {"days": 30, "interval_minutes": 1, "seed": 42, "scenario": "humidity", "end": "2026-11-21T12:00:00Z"})
    generated = time.perf_counter()
    data = chart_data(rows_in_range(root, run["id"], run["loggers"][0]["id"]), 1)
    charted = time.perf_counter()
    export = csv_text(rows_in_range(root, run["id"], run["loggers"][0]["id"]))
    exported = time.perf_counter()
    report = {"platform": platform.machine(), "python": platform.python_version(), "days": 30, "interval_minutes": 1,
              "loggers": 3, "generated_rows": sum(item["count"] for item in run["loggers"]),
              "generate_seconds": round(generated-started, 3), "chart_query_seconds": round(charted-generated, 3),
              "export_seconds": round(exported-charted, 3), "chart_raw_rows": data["raw_count"], "chart_points": len(data["points"]),
              "export_bytes": len(export.encode("utf-8")), "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "scope": "DeskPi synthetic local benchmark; not SMApi, BLE or concurrent HTTP load"}
    print(json.dumps(report, indent=2))
