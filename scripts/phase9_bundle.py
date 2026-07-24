from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from src.research.phase9 import Phase9Config, run_phase9_scanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 9 cross-market opportunity scanner")
    parser.add_argument("--data-root", type=Path, default=Path("data/validated"))
    parser.add_argument("--output", type=Path, default=Path("reports/phase9"))
    parser.add_argument("--symbols", nargs="*", default=[])
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--account-equity", type=float, default=100_000.0)
    parser.add_argument("--stock-entry-score", type=float, default=None)
    parser.add_argument("--crypto-entry-score", type=float, default=None)
    args = parser.parse_args()

    base = Phase9Config()
    stock_profile = base.stock_profile
    crypto_profile = base.crypto_profile
    if args.stock_entry_score is not None:
        stock_profile = replace(stock_profile, entry_score=args.stock_entry_score)
    if args.crypto_entry_score is not None:
        crypto_profile = replace(crypto_profile, entry_score=args.crypto_entry_score)
    config = replace(
        base,
        symbols=tuple(args.symbols),
        top_n_per_market=args.top_n,
        account_equity=args.account_equity,
        output_root=args.output,
        stock_profile=stock_profile,
        crypto_profile=crypto_profile,
    )
    result = run_phase9_scanner(args.data_root, config)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
