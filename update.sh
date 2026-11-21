#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 tools/process_status.py require-stopped
if [[ -n $(git status --porcelain) ]]; then
  echo 'Update abgebrochen: lokale Änderungen zuerst prüfen und sichern.' >&2
  exit 1
fi
git pull --ff-only
./install.sh
python3 -m unittest discover -s tests -v
