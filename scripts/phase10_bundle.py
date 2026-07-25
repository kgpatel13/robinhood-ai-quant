from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from src.research.phase10 import Phase10Config, run_phase10_replay


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase 10.4 final robustness validation replay"
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/validated"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase10"))
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--signal-stride", type=int, default=1)
    parser.add_argument("--primary-holding-period", type=int, default=5)
    parser.add_argument(
        "--same-bar-policy",
        choices=("conservative", "optimistic", "ambiguous"),
        default="conservative",
    )
    parser.add_argument("--threshold-only", action="store_true")
    parser.add_argument("--stock-entry-score", type=float, default=None)
    parser.add_argument("--crypto-entry-score", type=float, default=None)
    args = parser.parse_args()

    base = Phase10Config()
    stock = base.stock_profile
    crypto = base.crypto_profile
    if args.stock_entry_score is not None:
        stock = replace(stock, entry_score=args.stock_entry_score)
    if args.crypto_entry_score is not None:
        crypto = replace(crypto, entry_score=args.crypto_entry_score)
    config = replace(
        base,
        symbols=tuple(args.symbols),
        output_root=args.output,
        signal_stride=args.signal_stride,
        primary_holding_period=args.primary_holding_period,
        same_bar_policy=args.same_bar_policy,
        include_below_threshold=not args.threshold_only,
        stock_profile=stock,
        crypto_profile=crypto,
    )
    result = run_phase10_replay(args.data_root, config)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
