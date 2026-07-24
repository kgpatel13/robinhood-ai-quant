from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.research.phase8 import write_diagnostic_reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 8 diagnostics from Phase 7")
    parser.add_argument("--promotion-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/phase8/diagnostics"))
    args = parser.parse_args()
    print(json.dumps(write_diagnostic_reports(args.promotion_report, args.output), indent=2))


if __name__ == "__main__":
    main()
