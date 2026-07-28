from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

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

st.set_page_config(page_title="Atlas Control Center", page_icon="📈", layout="wide")

PROFILE_DIR = ROOT / "config" / "profiles"
store = ProfileStore(PROFILE_DIR)


def default_profile() -> ControlCenterProfile:
    return ControlCenterProfile()


def synthetic_bars(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    index = pd.date_range(end=datetime.now(UTC), periods=40, freq="min")
    result: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(symbols):
        base = 100.0 + offset * 10
        close = pd.Series([base + i * (0.04 + offset * 0.005) for i in range(40)], index=index)
        result[symbol] = pd.DataFrame(
            {
                "open": close - 0.03,
                "high": close + 0.06,
                "low": close - 0.06,
                "close": close,
                "volume": [1000.0 + i * 15 + offset * 20 for i in range(40)],
            },
            index=index,
        )
    return result


st.title("Atlas AI Trading Control Center")
st.caption(
    "Phase 6.3–6.5 · Multi-symbol intelligence · Portfolio safeguards · Persistent paper state"
)
st.error("MODE: PAPER ONLY · LIVE BROKER: DISABLED · ORDER SUBMISSION: UNAVAILABLE")

with st.sidebar:
    st.header("Configuration")
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
snapshot = service.create_snapshot(synthetic_bars(symbols), state, as_of=datetime.now(UTC))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Engine mode", snapshot.mode)
col2.metric("Open positions", snapshot.open_positions)
col3.metric("Trades today", snapshot.trades_today)
col4.metric("Realized P&L", f"${snapshot.realized_pnl:,.2f}")

tabs = st.tabs(["Opportunity Monitor", "Risk Controls", "Positions", "Profiles", "System Health"])
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
with tabs[2]:
    st.info("No paper positions are open in the demonstration session.")
with tabs[3]:
    st.write("Saved profile files")
    st.code("\n".join(store.list_profiles()) or "No profiles saved yet")
with tabs[4]:
    st.success("Control-center services operational")
    st.write(
        {
            "as_of": snapshot.as_of.isoformat(),
            "halted": snapshot.halted,
            "paper_only": profile.paper_only,
        }
    )
