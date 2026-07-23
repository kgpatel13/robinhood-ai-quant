#!/usr/bin/env bash
set -euo pipefail
python -m src.main plugin-list
python -m src.main config-validate
python -m pytest -q \
  tests/unit/test_plugins.py \
  tests/unit/test_services.py \
  tests/unit/test_events.py \
  tests/unit/test_discovery.py \
  tests/unit/test_runtime.py \
  tests/integration/test_plugin_cli.py
echo "Phase 4.5 architecture smoke test passed."
