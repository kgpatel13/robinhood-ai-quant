Atlas Phase 4.5 - Historical Replay and Walk-Forward Validation

New capabilities:
- rolling train/test walk-forward replay
- optimizer selection using training data only
- transaction-cost-adjusted out-of-sample returns
- per-window constraint validation
- market regime classification
- asset-level performance attribution
- deterministic reports and diagnostics

Important research limitation:
The current ranked-assets input is a static candidate snapshot. The replay prevents
future returns from entering weight optimization, but fully point-in-time universe
validation requires historical ranked-asset snapshots. This limitation is explicitly
recorded in walk_forward_diagnostics.json.

Validation:
python -m ruff check src tests scripts
python -m mypy src
python -m pytest

Run:
python -m scripts.atlas_v4_walk_forward --capital 100000

For shorter available history:
python -m scripts.atlas_v4_walk_forward --training-observations 126 --testing-observations 42 --step-observations 42
