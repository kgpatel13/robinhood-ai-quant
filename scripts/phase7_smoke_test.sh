#!/usr/bin/env bash
set -euo pipefail
python -m compileall -q src scripts tests
python -m pytest
ruff check .
ruff format --check .
mypy src
echo "Phase 7 quality gate passed."
