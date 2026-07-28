from datetime import UTC, datetime

from src.control_center import (
    CandidateStatus,
    IntradayPortfolioRiskEngine,
    IntradaySessionState,
    RankedCandidate,
    RiskLimits,
)


def candidate() -> RankedCandidate:
    return RankedCandidate(
        "AAPL", "intraday_momentum", 0.8, CandidateStatus.ELIGIBLE, 0.08, sector="Technology"
    )


def test_risk_engine_approves_valid_candidate() -> None:
    state = IntradaySessionState("2026-07-27", 100_000.0)
    result = IntradayPortfolioRiskEngine(RiskLimits()).evaluate(
        candidate(), state, as_of=datetime.now(UTC)
    )
    assert result.approved
    assert result.approved_weight == 0.08


def test_risk_engine_blocks_daily_loss() -> None:
    state = IntradaySessionState("2026-07-27", 100_000.0, realized_pnl=-2_000.0)
    result = IntradayPortfolioRiskEngine(RiskLimits()).evaluate(
        candidate(), state, as_of=datetime.now(UTC)
    )
    assert not result.approved
    assert "maximum daily loss reached" in result.reasons


def test_duplicate_symbol_is_blocked() -> None:
    from src.control_center import PaperPosition

    state = IntradaySessionState("2026-07-27", 100_000.0)
    state.positions["AAPL"] = PaperPosition("AAPL", 10, 100, 101, "intraday_momentum", "Technology")
    result = IntradayPortfolioRiskEngine(RiskLimits()).evaluate(
        candidate(), state, as_of=datetime.now(UTC)
    )
    assert not result.approved
    assert "symbol already held" in result.reasons
