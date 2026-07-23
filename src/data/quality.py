from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from src.data.schema import BAR_COLUMNS, normalize_bars


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    code: str
    message: str
    count: int = 1


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    rows: int
    symbols: int
    start: str | None
    end: str | None
    issues: tuple[QualityIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["issues"] = [asdict(issue) for issue in self.issues]
        return payload


class DataQualityValidator:
    def __init__(self, minimum_rows: int = 2) -> None:
        self.minimum_rows = minimum_rows

    def validate(self, frame: pd.DataFrame) -> QualityReport:
        issues: list[QualityIssue] = []
        missing = [column for column in BAR_COLUMNS if column not in frame.columns]
        if missing:
            issues.append(QualityIssue("error", "missing_columns", str(missing), len(missing)))
            return QualityReport(False, len(frame), 0, None, None, tuple(issues))
        normalized = normalize_bars(frame)
        if len(normalized) < self.minimum_rows:
            issues.append(QualityIssue("error", "insufficient_rows", "Too few observations"))
        duplicate_count = int(normalized.duplicated(["symbol", "timestamp"]).sum())
        if duplicate_count:
            issues.append(QualityIssue("error", "duplicate_bars", "Duplicate symbol/timestamp rows", duplicate_count))
        null_count = int(normalized[["open", "high", "low", "close", "volume"]].isna().sum().sum())
        if null_count:
            issues.append(QualityIssue("error", "null_ohlcv", "Null OHLCV values", null_count))
        negative_volume = int((normalized["volume"] < 0).sum())
        if negative_volume:
            issues.append(QualityIssue("error", "negative_volume", "Negative volume values", negative_volume))
        invalid_ohlc = (
            (normalized["high"] < normalized[["open", "close", "low"]].max(axis=1))
            | (normalized["low"] > normalized[["open", "close", "high"]].min(axis=1))
            | (normalized[["open", "high", "low", "close", "adj_close"]] <= 0).any(axis=1)
        )
        invalid_count = int(invalid_ohlc.sum())
        if invalid_count:
            issues.append(QualityIssue("error", "invalid_ohlc", "Inconsistent or non-positive prices", invalid_count))
        for symbol, group in normalized.groupby("symbol", observed=True):
            if not group["timestamp"].is_monotonic_increasing:
                issues.append(QualityIssue("error", "unsorted_timestamps", f"Timestamps not sorted for {symbol}"))
        errors = [issue for issue in issues if issue.severity == "error"]
        start = normalized["timestamp"].min().isoformat() if not normalized.empty else None
        end = normalized["timestamp"].max().isoformat() if not normalized.empty else None
        return QualityReport(
            passed=not errors, rows=len(normalized), symbols=normalized["symbol"].nunique(),
            start=start, end=end, issues=tuple(issues),
        )
