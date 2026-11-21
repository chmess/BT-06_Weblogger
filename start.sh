#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -x .venv/bin/python ]]; then py=.venv/bin/python; else py=python3; fi
exec "$py" app.py serve "$@"
