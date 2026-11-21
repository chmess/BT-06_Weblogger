#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 erforderlich"'
mkdir -p config runtime simulation logs data
if [[ $# == 0 ]]; then
  python3 -c 'from zoneinfo import ZoneInfo; ZoneInfo("Europe/Berlin"); import backend.server; print("Linux-Weboberfläche startbereit. Keine Zusatzpakete nötig. Start: ./start.sh")'
elif [[ $# == 1 && $1 == --ble ]]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements-ble.txt
else
  echo 'Verwendung: ./install.sh [--ble]' >&2
  exit 2
fi
