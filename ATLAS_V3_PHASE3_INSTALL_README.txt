Atlas AI v3.0 Phase 3 - Universe-Scale Research Engine
======================================================

This patch adds deterministic universe batching, resumable batch history updates,
parallel history downloads, parallel feature computation, and history coverage
inventory reporting.

Install
-------
Extract this ZIP into the project root and allow overwrite.

Validation
----------
python -m pytest tests/test_atlas_scaling.py tests/test_atlas_history.py tests/test_atlas_market.py
python -m pytest
python -m ruff check src tests scripts
python -m mypy src

Recommended first production-safe batch
---------------------------------------
python -m scripts.atlas_v3_universe_scale --stock-limit 1000 --crypto-limit 250 --batch-size 250 --offset 0 --workers 8 2>&1 | Tee-Object -FilePath .\reports\atlas_v3\v3_phase3_batch_000_console.txt

Continue subsequent batches by changing offset:
--offset 250
--offset 500
--offset 750

Use --stock-limit 0 or --crypto-limit 0 to request all eligible assets.
Use --skip-history to rebuild features from history already on disk.

After each batch, rerun Phase 2 ranking:
python -m scripts.atlas_v3_alpha_ranking --top-n 100 --bottom-n 25

Primary Phase 3 report:
reports\atlas_v3\universe_scale_summary.json
