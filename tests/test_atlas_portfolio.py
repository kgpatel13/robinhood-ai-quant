from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.atlas.portfolio import (
    CurrentPosition,
    PortfolioCandidate,
    PortfolioConfig,
    PortfolioEngine,
    write_reports,
)


def _candidate(
    rank: int,
    symbol: str,
    percentile: float,
    asset_class: str = "stock",
    volatility: float | None = 0.25,
    price: float | None = 100.0,
) -> PortfolioCandidate:
    return PortfolioCandidate(
        rank=rank,
        asset_id=f"{asset_class}:{symbol}",
        symbol=symbol,
        asset_class=asset_class,
        alpha_score=1.0 / rank,
        alpha_percentile=percentile,
        confidence="high" if percentile >= 0.9 else "medium",
        volatility_60d=volatility,
        price=price,
    )


def test_construct_respects_cash_position_and_crypto_limits() -> None:
    candidates = [
        _candidate(1, "BTC", 0.99, "crypto", 0.50),
        _candidate(2, "AAA", 0.98),
        _candidate(3, "BBB", 0.97),
        _candidate(4, "CCC", 0.96),
    ]
    config = PortfolioConfig(
        capital=10_000,
        cash_reserve_pct=0.10,
        max_positions=4,
        max_position_pct=0.30,
        max_crypto_pct=0.15,
    )
    result = PortfolioEngine(config).construct(candidates)
    assert result.metrics.position_count == 4
    assert result.metrics.cash_weight == pytest.approx(0.10)
    assert result.metrics.crypto_weight <= 0.15 + 1e-9
    assert result.metrics.largest_position_weight <= 0.30 + 1e-9


def test_candidate_filters_and_position_limit() -> None:
    candidates = [
        _candidate(1, "AAA", 0.95),
        _candidate(2, "BBB", 0.85),
        _candidate(3, "CCC", 0.65),
    ]
    config = PortfolioConfig(max_positions=1, minimum_alpha_percentile=0.70)
    result = PortfolioEngine(config).construct(candidates)
    assert [position.symbol for position in result.targets] == ["AAA"]
    assert result.excluded["stock:BBB"] == "outside_position_limit"
    assert result.excluded["stock:CCC"] == "below_minimum_alpha_percentile"


def test_rebalance_generates_buy_hold_trim_and_sell() -> None:
    candidates = [
        _candidate(1, "AAA", 0.99),
        _candidate(2, "BBB", 0.98),
        _candidate(3, "CCC", 0.97),
    ]
    config = PortfolioConfig(
        capital=10_000,
        cash_reserve_pct=0.10,
        max_positions=3,
        max_position_pct=0.40,
        rebalance_threshold_pct=0.01,
        sizing_method="equal",
    )
    current = [
        CurrentPosition("stock:AAA", "AAA", "stock", 3_000),
        CurrentPosition("stock:BBB", "BBB", "stock", 4_500),
        CurrentPosition("stock:OLD", "OLD", "stock", 1_000),
    ]
    result = PortfolioEngine(config).construct(candidates, current)
    actions = {action.symbol: action.action for action in result.actions}
    assert actions == {"AAA": "HOLD", "BBB": "TRIM", "CCC": "BUY", "OLD": "SELL"}


def test_report_writer_marks_orders_as_paper_only(tmp_path: Path) -> None:
    result = PortfolioEngine(PortfolioConfig(max_positions=1)).construct(
        [_candidate(1, "AAA", 0.99)]
    )
    artifacts = write_reports(result, tmp_path)
    payload = json.loads(Path(artifacts["orders_preview"]).read_text(encoding="utf-8"))
    assert payload["paper_only"] is True
    assert len(payload["orders"]) == 1


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError, match="capital"):
        PortfolioConfig(capital=0)


def test_hybrid_falls_back_and_effective_positions_are_normalized() -> None:
    candidates = [
        _candidate(1, "AAA", 0.99, volatility=None, price=None),
        _candidate(2, "BBB", 0.98, volatility=None, price=None),
    ]
    result = PortfolioEngine(
        PortfolioConfig(max_positions=2, cash_reserve_pct=0.10, sizing_method="hybrid")
    ).construct(candidates)
    assert result.diagnostics.effective_sizing_method == "score"
    assert result.diagnostics.sizing_fallback_reason == "volatility_unavailable"
    assert result.metrics.effective_positions <= result.metrics.position_count
    assert result.metrics.price_coverage == 0.0


def test_sector_limit_applies_when_metadata_exists() -> None:
    candidates = [
        PortfolioCandidate(
            rank=1,
            asset_id="stock:AAA",
            symbol="AAA",
            asset_class="stock",
            alpha_score=1.0,
            alpha_percentile=0.99,
            confidence="high",
            volatility_60d=0.2,
            price=100.0,
            sector="Technology",
        ),
        PortfolioCandidate(
            rank=2,
            asset_id="stock:BBB",
            symbol="BBB",
            asset_class="stock",
            alpha_score=0.9,
            alpha_percentile=0.98,
            confidence="high",
            volatility_60d=0.2,
            price=100.0,
            sector="Technology",
        ),
        PortfolioCandidate(
            rank=3,
            asset_id="stock:CCC",
            symbol="CCC",
            asset_class="stock",
            alpha_score=0.8,
            alpha_percentile=0.97,
            confidence="high",
            volatility_60d=0.2,
            price=100.0,
            sector="Healthcare",
        ),
    ]
    config = PortfolioConfig(
        max_positions=3,
        cash_reserve_pct=0.10,
        max_position_pct=0.50,
        max_sector_pct=0.60,
        sizing_method="equal",
    )
    result = PortfolioEngine(config).construct(candidates)
    tech_weight = sum(
        position.target_weight for position in result.targets if position.sector == "Technology"
    )
    assert tech_weight <= 0.60 + 1e-9
