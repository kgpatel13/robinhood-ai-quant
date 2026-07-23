from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class CatalogEntry:
    asset_class: str
    symbol: str
    rows: int
    start: str
    end: str
    source: str
    path: str


def build_catalog(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not root.exists():
        return entries
    for path in sorted(root.glob("*/*.parquet")):
        frame = pd.read_parquet(path, columns=["timestamp", "symbol", "source"])
        if frame.empty:
            continue
        timestamps = pd.to_datetime(frame["timestamp"], utc=True)
        entry = CatalogEntry(
            asset_class=path.parent.name,
            symbol=str(frame["symbol"].iloc[0]),
            rows=len(frame),
            start=timestamps.min().isoformat(),
            end=timestamps.max().isoformat(),
            source=",".join(sorted(frame["source"].astype(str).unique())),
            path=str(path),
        )
        entries.append(asdict(entry))
    return entries
