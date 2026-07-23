from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import yaml

from src.research import (
    OptimizationConfig,
    ParameterSpec,
    WalkForwardConfig,
    run_phase5_bundle,
)
from src.research.models import ObjectiveName


def main() -> None:
    parser = argparse.ArgumentParser(description="Run complete Phase 5 research validation bundle")
    parser.add_argument("--config", type=Path, default=Path("config/phase5.yaml"))
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    payload = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    optimization_payload = payload["optimization"]
    parameters = tuple(
        ParameterSpec(name=name, values=tuple(values))
        for name, values in optimization_payload["parameters"].items()
    )
    equity_costs = payload["costs"]["equity"]
    optimization = OptimizationConfig(
        strategy=str(optimization_payload["strategy"]),
        parameters=parameters,
        objective=cast(ObjectiveName, str(optimization_payload["objective"])),
        workers=int(optimization_payload["workers"]),
        initial_cash=float(optimization_payload["initial_cash"]),
        commission_per_trade=float(equity_costs["commission_per_trade"]),
        slippage_bps=float(equity_costs["slippage_bps"]),
    )
    wf_payload = payload["walk_forward"]
    walk_forward = WalkForwardConfig(
        training_years=int(wf_payload["training_years"]),
        testing_years=int(wf_payload["testing_years"]),
        step_years=int(wf_payload["step_years"]),
        minimum_test_rows=int(wf_payload["minimum_test_rows"]),
    )
    result = run_phase5_bundle(
        data_root=Path(payload["data"]["root"]),
        symbols=args.symbols or list(payload["data"]["symbols"]),
        optimization=optimization,
        walk_forward=walk_forward,
        output_root=args.output or Path(payload["outputs"]["directory"]),
        crypto_fee_bps=float(payload["costs"]["crypto"]["fee_bps"]),
        crypto_slippage_bps=float(payload["costs"]["crypto"]["slippage_bps"]),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
