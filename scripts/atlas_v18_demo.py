from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from src.atlas_v18 import (
    AtlasV18DecisionEngine,
    LiveSafetyState,
    MarketRegime,
    SignalAction,
    StrategySignal,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safe ATLAS v18 decision-engine demo.")
    parser.add_argument("--equity", type=float, default=100_000.0)
    args = parser.parse_args()
    prices = [100.0 + index * 0.35 for index in range(25)]
    signals = [
        StrategySignal(
            "momentum",
            SignalAction.BUY,
            0.82,
            rationale="positive momentum",
            regime_affinity=frozenset({MarketRegime.TRENDING_BULL}),
        ),
        StrategySignal("breakout", SignalAction.BUY, 0.74, rationale="range breakout"),
        StrategySignal("mean_reversion", SignalAction.WAIT, 0.55, rationale="no reversal"),
    ]
    decision = AtlasV18DecisionEngine().evaluate(
        prices=prices,
        signals=signals,
        equity=args.equity,
        safety_state=LiveSafetyState(),
    )
    print(json.dumps(asdict(decision), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
