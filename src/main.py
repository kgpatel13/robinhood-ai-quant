from __future__ import annotations

import argparse
import json
import logging
import sys

from src.common.config import load_settings, validate_all_configs
from src.common.exceptions import QuantPlatformError
from src.common.health import collect_health
from src.common.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quant-platform")
    parser.add_argument(
        "command",
        choices=("healthcheck", "config-validate", "show-config"),
    )
    return parser


def run(command: str) -> int:
    settings = load_settings()
    configure_logging(settings.log_level, settings.logs_dir)

    if command == "healthcheck":
        print(json.dumps(collect_health(settings), indent=2))
        return 0

    configs = validate_all_configs(settings.config_dir)

    if command == "config-validate":
        print(f"Configuration validation passed: {len(configs)} files")
        return 0

    if command == "show-config":
        print(json.dumps(configs, indent=2))
        return 0

    raise ValueError(f"Unsupported command: {command}")


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = run(args.command)
    except (QuantPlatformError, OSError, ValueError) as exc:
        LOGGER.error("%s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
