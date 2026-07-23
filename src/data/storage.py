from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd

from src.data.schema import normalize_bars

ParquetCompression = Literal["snappy", "gzip", "brotli", "lz4", "zstd"]
_ALLOWED_COMPRESSIONS: frozenset[str] = frozenset(
    {"snappy", "gzip", "brotli", "lz4", "zstd"}
)


class ParquetBarStore:
    def __init__(self, root: Path, compression: str = "snappy") -> None:
        if compression not in _ALLOWED_COMPRESSIONS:
            allowed = ", ".join(sorted(_ALLOWED_COMPRESSIONS))
            raise ValueError(
                f"Unsupported parquet compression '{compression}'. "
                f"Allowed values: {allowed}."
            )

        self.root = root
        self.compression = cast(ParquetCompression, compression)

    def path_for(self, asset_class: str, symbol: str) -> Path:
        safe_symbol = symbol.upper().replace("/", "-")
        return self.root / asset_class / f"{safe_symbol}.parquet"

    def write(self, frame: pd.DataFrame, asset_class: str, symbol: str) -> Path:
        normalized = normalize_bars(frame)
        path = self.path_for(asset_class, symbol)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = pd.read_parquet(path)
            normalized = normalize_bars(
                pd.concat([existing, normalized], ignore_index=True)
            )
            normalized = normalized.drop_duplicates(
                ["symbol", "timestamp"], keep="last"
            )

        normalized.to_parquet(
            path,
            index=False,
            compression=self.compression,
        )
        self._write_manifest(path, normalized)
        return path

    def read(self, asset_class: str, symbol: str) -> pd.DataFrame:
        path = self.path_for(asset_class, symbol)
        if not path.exists():
            raise FileNotFoundError(path)
        return normalize_bars(pd.read_parquet(path))

    def _write_manifest(self, path: Path, frame: pd.DataFrame) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "file": path.name,
            "sha256": digest,
            "rows": len(frame),
            "symbols": sorted(frame["symbol"].astype(str).unique().tolist()),
            "start": frame["timestamp"].min().isoformat(),
            "end": frame["timestamp"].max().isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        path.with_suffix(".manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
