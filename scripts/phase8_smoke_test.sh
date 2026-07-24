#!/usr/bin/env bash
set -euo pipefail
python -m compileall -q src scripts
pytest
ruff check .
ruff format --check .
mypy src
echo "Phase 8 quality gate passed."
