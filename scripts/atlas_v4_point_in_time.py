from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.atlas.portfolio.point_in_time import (
    PointInTimeConfig,
    build_point_in_time_snapshots,
)
from src.atlas.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atlas Phase 4.6 point-in-time snapshot and leakage-audit engine"
    )
    parser.add_argument("--history", type=Path, default=Path("data/market/daily"))
    parser.add_argument("--metadata", type=Path, default=Path("data/market/metadata.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/atlas_v4/point_in_time"),
    )
    parser.add_argument("--minimum-history-observations", type=int, default=126)
    parser.add_argument("--rebalance-observations", type=int, default=63)
    parser.add_argument("--maximum-assets", type=int)
    parser.add_argument("--minimum-price", type=float, default=3.0)
    parser.add_argument("--maximum-absolute-daily-return", type=float, default=0.50)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = PointInTimeConfig(
        minimum_history_observations=args.minimum_history_observations,
        rebalance_observations=args.rebalance_observations,
        maximum_assets=args.maximum_assets,
        minimum_price=args.minimum_price,
        maximum_absolute_daily_return=args.maximum_absolute_daily_return,
    )
    result = build_point_in_time_snapshots(
        args.history,
        args.output,
        args.metadata,
        config,
    )
    summary = {
        "complete": True,
        "paper_only": True,
        "platform_version": __version__,
        "phase": "4.6",
        "snapshot_count": len(result.snapshots),
        "first_snapshot": result.snapshots[0].as_of,
        "last_snapshot": result.snapshots[-1].as_of,
        "leakage_audit_passed": result.leakage_audit["passed"],
        "artifacts": {
            "snapshot_manifest": str(args.output / "snapshot_manifest.json"),
            "leakage_audit": str(args.output / "leakage_audit.json"),
            "snapshot_coverage": str(args.output / "snapshot_coverage.csv"),
            "snapshots": str(args.output / "snapshots"),
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
