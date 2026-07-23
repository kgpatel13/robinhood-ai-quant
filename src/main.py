from __future__ import annotations

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import sys

from src.common.config import load_settings, load_yaml, validate_all_configs
from src.common.exceptions import QuantPlatformError
from src.common.health import collect_health
from src.common.logging_config import configure_logging
from src.data.catalog import build_catalog
from src.data.demo import make_demo_bars
from src.data.service import MarketDataService
from src.data.storage import ParquetBarStore

LOGGER = logging.getLogger(__name__)


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-platform")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("healthcheck")
    sub.add_parser("config-validate")
    sub.add_parser("show-config")
    download = sub.add_parser("data-download")
    download.add_argument("--symbol", required=True)
    download.add_argument("--asset-class", choices=("stock", "crypto"), required=True)
    download.add_argument("--start", type=iso_date, required=True)
    download.add_argument("--end", type=iso_date, required=True)
    download.add_argument("--provider", choices=("yahoo", "coingecko"), default="yahoo")
    validate = sub.add_parser("data-validate")
    validate.add_argument("--path", type=Path, required=True)
    sub.add_parser("data-status")
    demo = sub.add_parser("data-demo")
    demo.add_argument("--symbol", default="DEMO")
    return parser


def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_logging(settings.log_level, settings.logs_dir)
    if args.command == "healthcheck":
        print(json.dumps(collect_health(settings), indent=2))
        return 0
    configs = validate_all_configs(settings.config_dir)
    if args.command == "config-validate":
        print(f"Configuration validation passed: {len(configs)} files")
        return 0
    if args.command == "show-config":
        print(json.dumps(configs, indent=2))
        return 0
    data_config = load_yaml(settings.config_dir / "data_sources.yaml")
    storage_config = data_config["storage"]
    validated_root = Path(str(storage_config["validated_directory"]))
    service = MarketDataService(data_config, validated_root)
    if args.command == "data-download":
        if args.end < args.start:
            raise ValueError("--end cannot be before --start")
        path, report = service.download(
            args.symbol, args.asset_class, args.start, args.end, args.provider
        )
        print(json.dumps({"path": str(path), "quality": report.to_dict()}, indent=2))
        return 0
    if args.command == "data-validate":
        report = service.validate_file(args.path)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.passed else 1
    if args.command == "data-status":
        print(json.dumps(build_catalog(validated_root), indent=2))
        return 0
    if args.command == "data-demo":
        store = ParquetBarStore(validated_root, str(storage_config.get("compression", "snappy")))
        path = store.write(make_demo_bars(args.symbol), "stock", args.symbol)
        print(json.dumps({"path": str(path), "mode": "offline-demo"}, indent=2))
        return 0
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = run(args)
    except (QuantPlatformError, OSError, ValueError) as exc:
        LOGGER.error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
