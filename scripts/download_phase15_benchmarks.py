from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


def _download(symbol: str, start: str, end: str | None, output: Path) -> None:
    frame = yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        actions=False,
    )
    if frame.empty:
        raise RuntimeError(f"no benchmark history returned for {symbol}")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    close_column = "Adj Close" if "Adj Close" in frame.columns else "Close"
    result = frame.reset_index()[["Date", close_column]].rename(
        columns={"Date": "timestamp", close_column: "close"}
    )
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(f"saved {len(result):,} rows: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Phase 15.6 market benchmarks")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks"))
    args = parser.parse_args()
    _download("SPY", args.start, args.end, args.output / "SPY.csv")
    _download("BTC-USD", args.start, args.end, args.output / "BTC-USD.csv")


if __name__ == "__main__":
    main()
