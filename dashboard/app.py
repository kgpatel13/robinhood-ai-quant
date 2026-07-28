from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import (  # noqa: E402
    EquityJournal,
    compare_benchmark,
    position_exposure,
    rolling_metrics,
    strategy_attribution,
    summarize_equity,
    trade_replay,
)
from src.control_center import (  # noqa: E402
    AtlasControlCenterService,
    ControlCenterProfile,
    IntradaySessionState,
    ProfileStore,
    RiskLimits,
)
from src.intelligence import (  # noqa: E402
    AssistantContext,
    AtlasAssistant,
    ExplanationJournal,
    MultiTimeframeAnalyzer,
    TradeExplanationBuilder,
)
from src.paper_trading import (  # noqa: E402
    AutomatedPaperConfig,
    AutomatedPaperTrader,
    PaperAccountStore,
    PaperBroker,
    PaperBrokerConfig,
    PaperSessionConfig,
    RealMarketPaperSession,
    SessionStatus,
    YahooMarketDataFeed,
    YahooSignalDataProvider,
    build_daily_report,
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
EASTERN_TIME = ZoneInfo("America/New_York")


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
st.caption(
    "Phase 9.4–9.6 · Multi-Timeframe Intelligence · Explainable AI · Atlas Assistant · "
    "Regime intelligence · Display timezone: America/New_York (ET)"
)
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
        "Real-Market Paper",
        "Automated Paper",
        "Professional Analytics",
        "Risk Controls",
        "Positions",
        "Profiles",
        "System Health",
        "Atlas Intelligence",
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
        "Strategies",
        available_strategies(),
        default=["moving_average_cross", "rsi_mean_reversion"],
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
    st.subheader("Real-Market Paper Trading")
    st.warning(
        "This page uses real market quotes but only simulated fills. "
        "Live broker submission is unavailable."
    )
    paper_state_path = ROOT / "reports" / "paper" / "account.json"
    account_store = PaperAccountStore(paper_state_path)
    account = account_store.load(paper_capital)
    broker = PaperBroker(account, PaperBrokerConfig(commission_per_order=0.0, slippage_bps=2.0))
    feed = YahooMarketDataFeed(spread_bps=2.0)
    paper_session = RealMarketPaperSession(PaperSessionConfig(symbols), feed, broker, account_store)
    session_cols = st.columns(5)
    if session_cols[0].button("Start paper session", use_container_width=True):
        paper_session.start()
        st.session_state["paper_status"] = SessionStatus.RUNNING.value
    if session_cols[1].button("Pause", use_container_width=True):
        st.session_state["paper_status"] = SessionStatus.PAUSED.value
    if session_cols[2].button("Resume", use_container_width=True):
        st.session_state["paper_status"] = SessionStatus.RUNNING.value
    if session_cols[3].button("Refresh quotes", use_container_width=True):
        try:
            status = SessionStatus(
                st.session_state.get("paper_status", SessionStatus.STOPPED.value)
            )
            paper_session.status = status
            paper_snapshot = paper_session.cycle()
            st.session_state["paper_snapshot"] = paper_snapshot
            st.success("Real-market quotes refreshed; paper account marked to market")
        except Exception as exc:
            st.error(f"Market-data refresh failed: {exc}")
    if session_cols[4].button("Flatten paper positions", use_container_width=True):
        try:
            results = paper_session.flatten()
            st.success(f"Processed {len(results)} simulated flatten orders")
        except Exception as exc:
            st.error(f"Paper flatten failed: {exc}")

    paper_snapshot = st.session_state.get("paper_snapshot")
    if paper_snapshot is not None:
        metrics = st.columns(5)
        metrics[0].metric("Status", paper_snapshot.status.value.upper())
        metrics[1].metric("Paper equity", f"${paper_snapshot.equity:,.2f}")
        metrics[2].metric("Cash", f"${paper_snapshot.cash:,.2f}")
        metrics[3].metric("Unrealized P&L", f"${paper_snapshot.unrealized_pnl:,.2f}")
        metrics[4].metric("Open positions", paper_snapshot.open_positions)
        quote_rows = [
            {
                "Symbol": quote.symbol,
                "Bid": quote.bid,
                "Ask": quote.ask,
                "Last": quote.last,
                "Source": quote.source,
                "Timestamp (ET)": quote.timestamp.astimezone(EASTERN_TIME),
            }
            for quote in paper_snapshot.quotes.values()
        ]
        st.dataframe(pd.DataFrame(quote_rows), use_container_width=True, hide_index=True)
        if paper_snapshot.messages:
            st.code("\n".join(paper_snapshot.messages))
    else:
        st.info(
            "Click Refresh quotes to load current Yahoo minute data and mark the "
            "persisted paper account to market."
        )

    report = build_daily_report(account, datetime.now(UTC))
    st.subheader("Persisted paper account")
    st.json(report.summary)
    if not report.positions.empty:
        st.dataframe(report.positions, use_container_width=True, hide_index=True)
    st.download_button(
        "Download paper order journal",
        report.orders.to_csv(index=False),
        "atlas_paper_orders.csv",
        "text/csv",
        disabled=report.orders.empty,
    )

with tabs[5]:
    st.subheader("Automated Strategy-to-Paper Execution")
    st.warning(
        "Automated cycles create simulated orders only. Live brokerage connectivity remains locked."
    )
    automated_strategy = st.selectbox(
        "Active automated strategy",
        available_strategies(),
        index=available_strategies().index("moving_average_cross"),
    )
    auto_cols = st.columns(4)
    target_fraction = auto_cols[0].number_input(
        "Target position (%)", min_value=0.5, max_value=20.0, value=5.0, step=0.5
    )
    auto_max_positions = auto_cols[1].number_input(
        "Maximum positions", min_value=1, max_value=20, value=5
    )
    auto_max_trades = auto_cols[2].number_input(
        "Maximum trades/day", min_value=1, max_value=100, value=12
    )
    auto_max_deployed = auto_cols[3].number_input(
        "Maximum deployed (%)", min_value=5.0, max_value=100.0, value=40.0, step=5.0
    )
    st.caption(
        "One cycle downloads recent strategy bars, evaluates the selected plugin, "
        "applies portfolio "
        "limits, submits simulated fills, persists the account, and journals portfolio equity."
    )
    if st.button("Run one automated paper cycle", type="primary", use_container_width=True):
        try:
            quotes = feed.latest_quotes(symbols)
            automated_account = account_store.load(paper_capital)
            automated_broker = PaperBroker(
                automated_account,
                PaperBrokerConfig(commission_per_order=0.0, slippage_bps=2.0),
            )
            automated = AutomatedPaperTrader(
                AutomatedPaperConfig(
                    symbols=symbols,
                    strategy_name=automated_strategy,
                    target_position_fraction=target_fraction / 100.0,
                    maximum_deployed_fraction=auto_max_deployed / 100.0,
                    maximum_open_positions=int(auto_max_positions),
                    maximum_trades_per_day=int(auto_max_trades),
                ),
                create_strategy(automated_strategy, **strategy_defaults(automated_strategy)),
                YahooSignalDataProvider(),
                automated_broker,
                account_store,
                EquityJournal(ROOT / "reports" / "paper" / "equity.jsonl"),
            )
            cycle_result = automated.cycle(quotes)
            st.session_state["automated_cycle_result"] = cycle_result
            st.success(
                f"Cycle completed: {len(cycle_result.orders)} simulated orders, "
                f"{cycle_result.open_positions} open positions"
            )
        except Exception as exc:
            st.error(f"Automated cycle failed safely: {exc}")
    automated_result = st.session_state.get("automated_cycle_result")
    if automated_result is not None:
        result_cols = st.columns(4)
        result_cols[0].metric("Equity", f"${automated_result.equity:,.2f}")
        result_cols[1].metric("Open positions", automated_result.open_positions)
        result_cols[2].metric("Orders this cycle", len(automated_result.orders))
        result_cols[3].metric("Signals evaluated", len(automated_result.signals))
        st.write("Latest signals", automated_result.signals)
        if automated_result.rejected:
            st.write("Rejected or skipped", automated_result.rejected)

with tabs[6]:
    st.subheader("Professional Paper-Trading Analytics")
    analytics_account = account_store.load(paper_capital)
    equity_frame = EquityJournal(ROOT / "reports" / "paper" / "equity.jsonl").load()
    if equity_frame.empty:
        st.info("Run automated paper cycles to build the persistent equity journal.")
    else:
        summary = summarize_equity(equity_frame["equity"])
        summary_cols = st.columns(6)
        summary_cols[0].metric("Total return", f"{summary.total_return:.2%}")
        summary_cols[1].metric("Annualized return", f"{summary.annualized_return:.2%}")
        summary_cols[2].metric("Volatility", f"{summary.annualized_volatility:.2%}")
        summary_cols[3].metric("Sharpe", f"{summary.sharpe_ratio:.2f}")
        summary_cols[4].metric("Maximum drawdown", f"{summary.maximum_drawdown:.2%}")
        summary_cols[5].metric("Observations", summary.observations)
        st.line_chart(equity_frame[["equity", "cash"]])
        rolling = rolling_metrics(equity_frame["equity"], window=min(20, len(equity_frame)))
        st.subheader("Rolling risk")
        st.line_chart(rolling[["rolling_sharpe", "drawdown"]])
        try:
            benchmark = HistoricalDataService.from_yahoo(
                HistoricalDataRequest(
                    "SPY",
                    equity_frame.index.min().date() - timedelta(days=7),
                    datetime.now(EASTERN_TIME).date() + timedelta(days=1),
                )
            )
            daily_equity = equity_frame["equity"].resample("1D").last().dropna()
            benchmark_close = benchmark["close"].reindex(daily_equity.index, method="ffill")
            comparison = compare_benchmark(daily_equity, benchmark_close)
            st.write(
                {
                    "portfolio_return": comparison.portfolio_return,
                    "SPY_return": comparison.benchmark_return,
                    "excess_return": comparison.excess_return,
                    "beta": comparison.beta,
                    "annualized_alpha": comparison.alpha_annualized,
                    "correlation": comparison.correlation,
                }
            )
        except Exception as exc:
            st.info(f"Benchmark comparison unavailable: {exc}")
    st.subheader("Current exposure")
    exposure = position_exposure(analytics_account)
    if exposure.empty:
        st.caption("No open paper positions")
    else:
        st.dataframe(exposure, use_container_width=True, hide_index=True)
    st.subheader("Strategy attribution")
    attribution = strategy_attribution(analytics_account)
    st.dataframe(attribution, use_container_width=True, hide_index=True)
    st.subheader("Trade replay")
    replay = trade_replay(analytics_account)
    st.dataframe(replay, use_container_width=True, hide_index=True)
    st.download_button(
        "Download trade replay",
        replay.to_csv(index=False),
        "atlas_trade_replay.csv",
        "text/csv",
        disabled=replay.empty,
    )

with tabs[7]:
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
with tabs[8]:
    st.info(
        "No control-center demonstration positions are open in this session. "
        "Real paper positions appear in the Real-Market Paper tab."
    )
with tabs[9]:
    st.write("Saved profile files")
    st.code("\n".join(store.list_profiles()) or "No profiles saved yet")
with tabs[10]:
    st.success("Research Lab, real-market paper services, and control-center services operational")
    st.write(
        {
            "version": "3.9.6",
            "as_of_et": snapshot.as_of.astimezone(EASTERN_TIME).isoformat(),
            "timezone": "America/New_York",
            "halted": snapshot.halted,
            "paper_only": profile.paper_only,
            "strategy_plugins": len(available_strategies()),
        }
    )


with tabs[11]:
    st.subheader("Multi-Timeframe Intelligence and Explainable AI")
    st.caption(
        "Local deterministic analysis only. This tab does not submit broker orders "
        "and does not call an external language model."
    )
    intelligence_symbol = st.text_input(
        "Intelligence symbol", "SPY", key="intelligence_symbol"
    ).upper()
    base = synthetic_daily_bars(400)
    frames = {
        "monthly": base.resample("ME").last().dropna(),
        "weekly": base.resample("W-FRI").last().dropna(),
        "daily": base,
        "hourly": synthetic_daily_bars(300),
        "intraday": synthetic_daily_bars(300),
    }
    assessment = MultiTimeframeAnalyzer().assess(intelligence_symbol, frames)
    intelligence_cols = st.columns(5)
    intelligence_cols[0].metric("Direction", assessment.direction.value.replace("_", " ").upper())
    intelligence_cols[1].metric("Entry quality", assessment.entry_quality.value.upper())
    intelligence_cols[2].metric("Aggregate score", f"{assessment.aggregate_score:+.3f}")
    intelligence_cols[3].metric("Confirmation", f"{assessment.confirmation_score:.0%}")
    intelligence_cols[4].metric("Conflict", f"{assessment.conflict_score:.0%}")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Timeframe": item.timeframe,
                    "Direction": item.direction.value,
                    "Score": item.score,
                    "Trend strength": item.trend_strength,
                    "Momentum": item.momentum,
                    "Volatility": item.volatility,
                    "Observations": item.observations,
                }
                for item in assessment.signals
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    explanation = TradeExplanationBuilder().build(
        assessment,
        regime="research_demo",
        model_probability=0.65,
        risk_reward_ratio=2.0,
    )
    st.markdown(f"**{explanation.summary}**")
    st.write("Reasons", assessment.reasons)
    st.write("Risk notes", explanation.risks)
    if st.button("Save explanation to audit journal"):
        ExplanationJournal(ROOT / "reports" / "intelligence" / "explanations.jsonl").append(
            explanation
        )
        st.success("Explanation saved")

    st.subheader("Atlas Assistant")
    question = st.text_input(
        "Ask about positions, losses, performance, strategies, or recorded explanations",
        "What is performance?",
    )
    if st.button("Ask Atlas Assistant", use_container_width=True):
        assistant_account = PaperAccountStore(ROOT / "reports" / "paper" / "account.json").load(
            paper_capital
        )
        position_rows = [
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "unrealized_pnl": position.unrealized_pnl,
            }
            for position in assistant_account.positions.values()
        ]
        explanation_rows = ExplanationJournal(
            ROOT / "reports" / "intelligence" / "explanations.jsonl"
        ).load(limit=50)
        answer = AtlasAssistant().answer(
            question,
            AssistantContext(
                positions=position_rows,
                explanations=explanation_rows,
                performance={
                    "paper equity": f"${assistant_account.equity:,.2f}",
                    "cash": f"${assistant_account.cash:,.2f}",
                    "open positions": len(assistant_account.positions),
                },
            ),
        )
        st.info(answer.answer)
        st.caption(f"Intent: {answer.intent} · Evidence records: {answer.evidence_count}")
