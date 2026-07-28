from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.control_center import (  # noqa: E402
    AtlasControlCenterService,
    ControlCenterProfile,
    IntradaySessionState,
    ProfileStore,
    RiskLimits,
)
from src.research_lab import (  # noqa: E402
    BacktestSettings,
    HistoricalDataRequest,
    HistoricalDataService,
    StrategyBacktestEngine,
    WalkForwardEngine,
)
from src.strategies.ensemble import EnsembleStrategy  # noqa: E402
from src.strategies.regime import AdaptiveMarketRegimeDetector  # noqa: E402
from src.strategies.registry import (  # noqa: E402
    available_strategies,
    create_strategy,
    strategy_defaults,
    strategy_metadata,
    strategy_parameter_space,
)

st.set_page_config(page_title="Atlas Research Lab", page_icon="📈", layout="wide")
PROFILE_DIR = ROOT / "config" / "profiles"
store = ProfileStore(PROFILE_DIR)


def synthetic_intraday_bars(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    index = pd.date_range(end=datetime.now(UTC), periods=80, freq="min")
    result: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(symbols):
        base = 100.0 + offset * 10
        close = pd.Series([base + i * (0.04 + offset * 0.005) for i in range(80)], index=index)
        result[symbol] = pd.DataFrame(
            {
                "open": close - 0.03,
                "high": close + 0.06,
                "low": close - 0.06,
                "close": close,
                "volume": [1000.0 + i * 15 + offset * 20 for i in range(80)],
            },
            index=index,
        )
    return result


def synthetic_daily_bars(length: int = 756) -> pd.DataFrame:
    index = pd.date_range(end=datetime.now(UTC).date(), periods=length, freq="B", tz="UTC")
    rng = np.random.default_rng(42)
    returns = rng.normal(0.00035, 0.012, length) + np.sin(np.arange(length) / 35) * 0.0015
    close = 100.0 * np.cumprod(1.0 + returns)
    return pd.DataFrame(
        {
            "open": close * (1.0 - 0.001),
            "high": close * (1.0 + 0.004),
            "low": close * (1.0 - 0.004),
            "close": close,
            "volume": rng.integers(800_000, 2_500_000, length),
        },
        index=index,
    )


def load_research_bars(
    source: str, symbol: str, start: date, end: date, upload: object
) -> pd.DataFrame:
    if source == "Synthetic demonstration":
        return synthetic_daily_bars()
    if source == "CSV upload":
        if upload is None:
            raise ValueError("Upload a CSV file before running the backtest")
        return HistoricalDataService.from_csv(upload)  # type: ignore[arg-type]
    return HistoricalDataService.from_yahoo(HistoricalDataRequest(symbol, start, end))


st.title("Atlas AI Trading Control Center")
st.caption("Phase 6.6–7.2 · Research Lab · Multi-strategy backtesting · Regime intelligence")
st.error("MODE: PAPER ONLY · LIVE BROKER: DISABLED · ORDER SUBMISSION: UNAVAILABLE")

with st.sidebar:
    st.header("Paper Configuration")
    profile_name = st.text_input("Profile name", "Regime-Adaptive Paper")
    paper_capital = st.number_input("Paper capital", min_value=1000.0, value=100000.0, step=5000.0)
    symbols_text = st.text_area("Symbols", "SPY, QQQ, AAPL, MSFT, NVDA")
    minimum_score = st.slider("Minimum candidate score", 0.0, 1.0, 0.55, 0.01)
    maximum_positions = st.slider("Maximum open positions", 1, 20, 5)
    maximum_trades = st.slider("Maximum trades per day", 1, 100, 12)
    maximum_daily_loss = st.slider("Maximum daily loss (%)", 0.1, 10.0, 1.5, 0.1)
    maximum_position = st.slider("Maximum position (%)", 1.0, 25.0, 8.0, 0.5)
    maximum_deployed = st.slider("Maximum deployed capital (%)", 5.0, 100.0, 40.0, 1.0)
    maximum_sector = st.slider("Maximum sector exposure (%)", 5.0, 100.0, 20.0, 1.0)
    save_profile = st.button("Save profile", use_container_width=True)

symbols = tuple(item.strip().upper() for item in symbols_text.split(",") if item.strip())
risk = RiskLimits(
    maximum_deployed_fraction=maximum_deployed / 100,
    maximum_position_fraction=maximum_position / 100,
    maximum_sector_fraction=maximum_sector / 100,
    maximum_open_positions=maximum_positions,
    maximum_trades_per_day=maximum_trades,
    maximum_daily_loss_fraction=maximum_daily_loss / 100,
)
profile = ControlCenterProfile(
    name=profile_name,
    paper_capital=paper_capital,
    symbols=symbols,
    minimum_candidate_score=minimum_score,
    risk=risk,
)
if save_profile:
    path = store.save(profile)
    st.sidebar.success(f"Saved {path.name}")

state = IntradaySessionState(datetime.now(UTC).date().isoformat(), paper_capital)
service = AtlasControlCenterService(profile)
snapshot = service.create_snapshot(synthetic_intraday_bars(symbols), state, as_of=datetime.now(UTC))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Engine mode", snapshot.mode)
col2.metric("Open positions", snapshot.open_positions)
col3.metric("Trades today", snapshot.trades_today)
col4.metric("Realized P&L", f"${snapshot.realized_pnl:,.2f}")

tabs = st.tabs(
    [
        "Opportunity Monitor",
        "Strategy Registry",
        "Backtest Lab",
        "Regime & Ensemble",
        "Risk Controls",
        "Positions",
        "Profiles",
        "System Health",
    ]
)

with tabs[0]:
    rows = [
        {
            "Symbol": item.candidate.symbol,
            "Strategy": item.candidate.strategy,
            "Score": round(item.candidate.score, 4),
            "Status": item.candidate.status.value,
            "Approved": item.approved,
            "Weight": round(item.approved_weight, 4),
            "Reason": "; ".join(item.reasons) or "eligible",
        }
        for item in snapshot.allocations
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Installed strategy plugins")
    registry_rows = []
    for name in available_strategies():
        metadata = strategy_metadata(name)
        registry_rows.append(
            {
                "Strategy": name,
                "Category": metadata.category,
                "Description": metadata.description,
                "Required History": metadata.required_history,
                "Defaults": strategy_defaults(name),
            }
        )
    st.dataframe(pd.DataFrame(registry_rows), use_container_width=True, hide_index=True)
    selected_plugin = st.selectbox("Inspect strategy parameters", available_strategies())
    parameter_rows = [
        {
            "Parameter": item.name,
            "Allowed research values": item.values,
            "Description": item.description,
        }
        for item in strategy_parameter_space(selected_plugin)
    ]
    st.dataframe(pd.DataFrame(parameter_rows), use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Historical Backtest Lab")
    left, middle, right = st.columns(3)
    source = left.selectbox(
        "Data source", ["Synthetic demonstration", "Yahoo Finance", "CSV upload"]
    )
    research_symbol = middle.text_input("Backtest symbol", "SPY").upper()
    selected_strategies = right.multiselect(
        "Strategies", available_strategies(), default=["moving_average_cross", "rsi_mean_reversion"]
    )
    date_left, date_right = st.columns(2)
    start_date = date_left.date_input("Start date", date.today() - timedelta(days=1095))
    end_date = date_right.date_input("End date", date.today())
    uploaded = (
        st.file_uploader("CSV with date/open/high/low/close/volume", type=["csv"])
        if source == "CSV upload"
        else None
    )
    c1, c2, c3, c4 = st.columns(4)
    initial_capital = c1.number_input("Initial capital", 1000.0, value=100000.0, step=5000.0)
    allocation = c2.slider("Capital allocation (%)", 1.0, 100.0, 100.0, 1.0)
    slippage = c3.number_input("Slippage (bps)", 0.0, value=2.0, step=0.5)
    commission = c4.number_input("Commission per order", 0.0, value=0.0, step=0.1)
    run_backtest = st.button("Run strategy comparison", type="primary", use_container_width=True)

    if run_backtest:
        try:
            bars = load_research_bars(source, research_symbol, start_date, end_date, uploaded)
            if not selected_strategies:
                raise ValueError("Select at least one strategy")
            engine = StrategyBacktestEngine(
                BacktestSettings(initial_capital, allocation / 100, commission, slippage)
            )
            comparison = engine.compare(bars, selected_strategies)
            summary = comparison.summary()
            st.session_state["research_bars"] = bars
            st.session_state["comparison"] = comparison
            st.success(
                f"Backtested {len(selected_strategies)} strategies across {len(bars):,} bars"
            )
            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total Return": st.column_config.NumberColumn(format="%.2f%%"),
                    "Annualized Return": st.column_config.NumberColumn(format="%.2f%%"),
                    "Maximum Drawdown": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )
        except Exception as exc:
            st.error(str(exc))

    comparison = st.session_state.get("comparison")
    if comparison is not None:
        equity = pd.concat([result.equity_curve for result in comparison.results], axis=1)
        drawdown = pd.concat([result.drawdown_curve for result in comparison.results], axis=1)
        st.subheader("Equity curves")
        st.line_chart(equity)
        st.subheader("Drawdown curves")
        st.line_chart(drawdown)
        strategy_for_trades = st.selectbox(
            "Trade ledger", [result.strategy for result in comparison.results]
        )
        result = next(item for item in comparison.results if item.strategy == strategy_for_trades)
        st.dataframe(result.trades, use_container_width=True, hide_index=True)
        st.download_button(
            "Download trade ledger CSV",
            result.trades.to_csv(index=False),
            f"{research_symbol}_{strategy_for_trades}_trades.csv",
            "text/csv",
        )

        bars_for_walk = st.session_state.get("research_bars")
        if bars_for_walk is not None and st.button("Run walk-forward validation"):
            try:
                folds = WalkForwardEngine().run(
                    bars_for_walk, strategy_for_trades, train_size=252, test_size=63
                )
                fold_rows = [
                    {
                        "Fold": fold.fold,
                        "Train End": fold.train_end,
                        "Test Start": fold.test_start,
                        "Test End": fold.test_end,
                        "Return": fold.result.total_return,
                        "Drawdown": fold.result.maximum_drawdown,
                        "Sharpe": fold.result.sharpe_ratio,
                    }
                    for fold in folds
                ]
                st.dataframe(pd.DataFrame(fold_rows), use_container_width=True, hide_index=True)
                if not folds:
                    st.warning("Not enough bars for a 252/63 walk-forward split")
            except Exception as exc:
                st.error(str(exc))

with tabs[3]:
    st.subheader("Market regime and strategy ensemble")
    demo = {
        symbol: synthetic_daily_bars(300) * (1.0 + offset * 0.001)
        for offset, symbol in enumerate(symbols)
    }
    assessment = AdaptiveMarketRegimeDetector().detect(demo, benchmark_symbol="SPY")
    regime_cols = st.columns(3)
    regime_cols[0].metric("Detected regime", assessment.regime.value)
    regime_cols[1].metric("Confidence", f"{assessment.confidence:.1%}")
    regime_cols[2].metric("Trading allowed", "YES" if assessment.trading_allowed else "NO")
    st.write("Allowed strategy families", assessment.allowed_strategies)
    st.json(dict(assessment.component_scores))
    ensemble_names = st.multiselect(
        "Ensemble members",
        available_strategies(),
        default=["moving_average_cross", "donchian_breakout"],
    )
    threshold = st.slider("Ensemble vote threshold", 0.1, 1.0, 0.5, 0.05)
    if ensemble_names:
        ensemble = EnsembleStrategy(
            tuple(create_strategy(name) for name in ensemble_names), threshold
        )
        st.success(f"Ensemble ready: {len(ensemble.strategies)} plugins, threshold {threshold:.2f}")
    else:
        st.info("Select at least one strategy to construct an ensemble")

with tabs[4]:
    st.json(
        {
            "maximum_deployed_fraction": risk.maximum_deployed_fraction,
            "maximum_position_fraction": risk.maximum_position_fraction,
            "maximum_sector_fraction": risk.maximum_sector_fraction,
            "maximum_open_positions": risk.maximum_open_positions,
            "maximum_trades_per_day": risk.maximum_trades_per_day,
            "maximum_daily_loss_fraction": risk.maximum_daily_loss_fraction,
            "maximum_consecutive_losses": risk.maximum_consecutive_losses,
            "cooldown_minutes": risk.cooldown_minutes,
        }
    )
with tabs[5]:
    st.info("No paper positions are open in this demonstration session.")
with tabs[6]:
    st.write("Saved profile files")
    st.code("\n".join(store.list_profiles()) or "No profiles saved yet")
with tabs[7]:
    st.success("Research Lab and control-center services operational")
    st.write(
        {
            "version": "3.7.2",
            "as_of": snapshot.as_of.isoformat(),
            "halted": snapshot.halted,
            "paper_only": profile.paper_only,
            "strategy_plugins": len(available_strategies()),
        }
    )
