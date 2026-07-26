from __future__ import annotations

import csv
import json
from pathlib import Path

from src.atlas.engine import run_atlas
from src.atlas.intelligence import detect_regime, score_opportunity
from src.atlas.models import AtlasConfig, MarketSnapshot


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="TEST",
        asset_class="stock",
        price=50.0,
        average_daily_volume=2_000_000.0,
        return_1d=0.03,
        return_5d=0.06,
        return_20d=0.12,
        volatility_20d=0.035,
        distance_from_20d_high=-0.02,
        relative_volume=2.0,
        spread_bps=5.0,
    )


def _write_universe(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "symbol",
                "price",
                "average_daily_volume",
                "return_1d",
                "return_5d",
                "return_20d",
                "volatility_20d",
                "distance_from_20d_high",
                "relative_volume",
                "spread_bps",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "symbol": symbol,
                "price": 50,
                "average_daily_volume": 2_000_000,
                "return_1d": 0.03,
                "return_5d": 0.06,
                "return_20d": 0.12,
                "volatility_20d": 0.035,
                "distance_from_20d_high": -0.02,
                "relative_volume": 2.0,
                "spread_bps": 5.0,
            }
        )


def test_detect_regime_and_strategy() -> None:
    snapshot = _snapshot()
    assert detect_regime(snapshot) == "bull_trend"
    scored = score_opportunity(snapshot)
    assert scored.strategy == "momentum_swing"
    assert 0 < scored.alpha_score <= 100
    assert scored.expected_holding_days <= 7


def test_run_atlas_creates_reproducible_artifacts(tmp_path: Path) -> None:
    stocks = tmp_path / "stocks.csv"
    crypto = tmp_path / "crypto.csv"
    baseline = tmp_path / "baseline.json"
    output = tmp_path / "reports"
    _write_universe(stocks, "AAA")
    _write_universe(crypto, "BTC-USD")
    baseline.write_text('{"approved": true}', encoding="utf-8")
    config = AtlasConfig(
        stock_universe_path=stocks,
        crypto_universe_path=crypto,
        baseline_signoff=baseline,
        output_root=output,
        experiment_root=output / "experiments",
    )

    first = run_atlas(config, project_root=tmp_path)
    second = run_atlas(config, project_root=tmp_path)

    assert first.experiment_id == second.experiment_id
    assert first.scanned_assets == 2
    assert first.diagnostics_passed
    assert not first.approved_for_paper_trading
    assert not first.approved_for_live_trading
    manifest = json.loads((output / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["baseline_fingerprint"]
    assert len(manifest["input_fingerprints"]) == 2
