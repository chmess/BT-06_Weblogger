#!/usr/bin/env python3
"""Offline import of a previously captured BT06 2.05 history; no BLE access."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.common.history_capture import read_capture
from backend.common.history_store import HistoryStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--device-id', required=True, help='Explizit zugeordnete achtstellige BT06-Kennung')
    parser.add_argument('--firmware', required=True, choices=['2.05'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = HistoryStore(args.root / 'data/history').publish(args.device_id, **read_capture(args.capture))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Historienimport fehlgeschlagen: {exc}\n')
    print(json.dumps({key: result[key] for key in ('id','count','duplicate','clock_verified','transport_complete')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
