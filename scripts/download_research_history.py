#!/usr/bin/env python
"""Download daily stock, ETF, and crypto history from Yahoo Finance.

Examples:
    python scripts/download_research_history.py
    python scripts/download_research_history.py --years 10
    python scripts/download_research_history.py --period max --groups etf crypto
    python scripts/download_research_history.py --symbols SPY QQQ BTC-USD
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

LOGGER = logging.getLogger("history_downloader")

UNIVERSE: dict[str, list[str]] = {
    "etf": [
        "SPY",
        "QQQ",
        "DIA",
        "IWM",
        "VTI",
        "VOO",
        "XLK",
        "XLF",
        "XLE",
        "XLI",
        "XLV",
        "XLP",
        "XLY",
        "XLU",
        "VNQ",
        "GLD",
        "SLV",
        "TLT",
        "IEF",
        "HYG",
        "LQD",
    ],
    "stock": [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "NFLX",
        "AMD",
        "AVGO",
        "JPM",
        "BAC",
        "GS",
        "CAT",
        "DE",
        "LLY",
        "UNH",
        "ABBV",
        "COST",
        "WMT",
        "KO",
        "PEP",
    ],
    "crypto": [
        "BTC-USD",
        "ETH-USD",
        "SOL-USD",
        "XRP-USD",
        "BNB-USD",
        "DOGE-USD",
        "ADA-USD",
        "LINK-USD",
        "AVAX-USD",
        "DOT-USD",
        "LTC-USD",
        "BCH-USD",
        "TRX-USD",
        "SHIB-USD",
    ],
}


@dataclass(frozen=True)
class DownloadResult:
    symbol: str
    group: str
    status: str
    rows: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    output_path: str = ""
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download normalized daily Yahoo Finance history to Parquet."
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=sorted(UNIVERSE),
        default=sorted(UNIVERSE),
        help="Universe groups to download.",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Optional explicit Yahoo ticker symbols. Overrides --groups.",
    )
    period_group = parser.add_mutually_exclusive_group()
    period_group.add_argument(
        "--period",
        default="max",
        choices=["1y", "2y", "5y", "10y", "max"],
        help="Yahoo history period. Default: max.",
    )
    period_group.add_argument(
        "--years",
        type=int,
        help="Explicit number of calendar years ending today.",
    )
    parser.add_argument("--interval", default="1d", choices=["1d", "1wk", "1mo"])
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/validated"),
    )
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--pause",
        type=float,
        default=1.0,
        help="Pause between successful symbols to reduce rate-limit risk.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing files. Otherwise existing data is merged and deduplicated.",
    )
    return parser.parse_args()


def symbol_group(symbol: str) -> str:
    if symbol in UNIVERSE["crypto"] or symbol.upper().endswith("-USD"):
        return "crypto"
    if symbol in UNIVERSE["etf"]:
        return "etf"
    return "stock"


def requested_symbols(args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.symbols:
        return [(symbol.upper(), symbol_group(symbol.upper())) for symbol in args.symbols]

    pairs: list[tuple[str, str]] = []
    for group in args.groups:
        pairs.extend((symbol, group) for symbol in UNIVERSE[group])
    return list(dict.fromkeys(pairs))


def normalize_history(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    frame = raw.reset_index()
    date_column = "Datetime" if "Datetime" in frame.columns else "Date"
    if date_column not in frame.columns:
        raise ValueError(f"Yahoo response has no Date/Datetime column: {list(frame.columns)}")

    frame = frame.rename(
        columns={
            date_column: "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        }
    )

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["symbol"] = symbol

    required = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Yahoo response missing required columns: {missing}")

    if "adjusted_close" not in frame.columns:
        frame["adjusted_close"] = frame["close"]

    result = frame[
        [
            "timestamp",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
        ]
    ].copy()

    numeric_columns = ["open", "high", "low", "close", "adjusted_close", "volume"]
    result[numeric_columns] = result[numeric_columns].apply(pd.to_numeric, errors="coerce")
    result = result.dropna(subset=["timestamp", "close"])
    result = result.drop_duplicates(subset=["timestamp"], keep="last")
    result = result.sort_values("timestamp").reset_index(drop=True)

    if result.empty:
        raise ValueError("No valid rows remained after normalization")
    if not result["timestamp"].is_monotonic_increasing:
        raise ValueError("Timestamps are not sorted")
    if (result["close"] <= 0).any():
        raise ValueError("History contains non-positive close prices")

    return result


def fetch_history(
    symbol: str,
    *,
    period: str,
    years: int | None,
    interval: str,
    retries: int,
) -> pd.DataFrame:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            kwargs: dict[str, object] = {
                "interval": interval,
                "auto_adjust": False,
                "actions": False,
                "repair": True,
                "timeout": 30,
                "raise_errors": True,
            }
            if years is not None:
                end = datetime.now(UTC) + timedelta(days=1)
                start = end - timedelta(days=365 * years + years // 4 + 5)
                kwargs["start"] = start.date().isoformat()
                kwargs["end"] = end.date().isoformat()
            else:
                kwargs["period"] = period

            return normalize_history(ticker.history(**kwargs), symbol)
        except Exception as exc:  # Yahoo/network failures vary by release.
            last_error = exc
            if attempt < retries:
                delay = min(30.0, 2.0 ** (attempt - 1))
                LOGGER.warning(
                    "%s attempt %s/%s failed: %s; retrying in %.1fs",
                    symbol,
                    attempt,
                    retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

    raise RuntimeError(f"{symbol} failed after {retries} attempts: {last_error}")


def merge_or_replace(path: Path, incoming: pd.DataFrame, overwrite: bool) -> pd.DataFrame:
    if path.exists() and not overwrite:
        existing = pd.read_parquet(path)
        existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
        combined = pd.concat([existing, incoming], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        return combined.sort_values("timestamp").reset_index(drop=True)
    return incoming


def save_manifest(results: Iterable[DownloadResult], output_root: Path) -> None:
    records = [result.__dict__ for result in results]
    manifest_dir = output_root / "_manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    pd.DataFrame(records).to_csv(
        manifest_dir / f"yahoo_download_{stamp}.csv",
        index=False,
    )
    failures = [record for record in records if record["status"] != "ok"]
    (manifest_dir / f"yahoo_failures_{stamp}.json").write_text(
        json.dumps(failures, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if args.years is not None and args.years < 1:
        raise SystemExit("--years must be at least 1")
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")

    symbols = requested_symbols(args)
    LOGGER.info("Downloading %s symbols", len(symbols))

    results: list[DownloadResult] = []
    for index, (symbol, group) in enumerate(symbols, start=1):
        LOGGER.info("[%s/%s] %s (%s)", index, len(symbols), symbol, group)
        try:
            history = fetch_history(
                symbol,
                period=args.period,
                years=args.years,
                interval=args.interval,
                retries=args.retries,
            )
            output_dir = args.output_root / group
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{symbol}.parquet"

            history = merge_or_replace(output_path, history, args.overwrite)
            history.to_parquet(output_path, index=False, compression="snappy")

            results.append(
                DownloadResult(
                    symbol=symbol,
                    group=group,
                    status="ok",
                    rows=len(history),
                    first_timestamp=history["timestamp"].iloc[0].isoformat(),
                    last_timestamp=history["timestamp"].iloc[-1].isoformat(),
                    output_path=str(output_path),
                )
            )
            LOGGER.info(
                "%s saved: %s rows, %s through %s",
                symbol,
                len(history),
                history["timestamp"].iloc[0].date(),
                history["timestamp"].iloc[-1].date(),
            )
        except Exception as exc:
            LOGGER.error("%s failed: %s", symbol, exc)
            results.append(
                DownloadResult(
                    symbol=symbol,
                    group=group,
                    status="failed",
                    error=str(exc),
                )
            )
        time.sleep(max(0.0, args.pause))

    save_manifest(results, args.output_root)
    successes = sum(result.status == "ok" for result in results)
    failures = len(results) - successes

    print(
        json.dumps(
            {
                "requested": len(results),
                "successful": successes,
                "failed": failures,
                "output_root": str(args.output_root),
            },
            indent=2,
        )
    )
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
