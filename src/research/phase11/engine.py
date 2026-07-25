from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from src.research.phase11.audit import audit_dataset
from src.research.phase11.dataset import build_symbol_dataset
from src.research.phase11.features import FEATURE_COLUMNS, build_phase11_features
from src.research.phase11.models import Phase11Config, Phase11Result


def _asset_class(path: Path) -> str:
    parent = path.parent.name.lower()
    return parent if parent in {"stock", "etf", "crypto"} else "stock"


def _discover(config: Phase11Config) -> list[Path]:
    files = sorted(config.data_root.rglob("*.parquet"))
    requested = {symbol.upper() for symbol in config.symbols}
    return [
        path
        for path in files
        if _asset_class(path) in config.asset_classes
        and (not requested or path.stem.upper() in requested)
    ]


def _write_json(payload: object, path: Path) -> str:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(path)


def build_phase11_dataset(config: Phase11Config) -> Phase11Result:
    config.output_root.mkdir(parents=True, exist_ok=True)
    config.dataset_path.parent.mkdir(parents=True, exist_ok=True)
    files = _discover(config)
    datasets: list[pd.DataFrame] = []
    failures: list[dict[str, str]] = []
    for path in files:
        try:
            raw = pd.read_parquet(path)
            features = build_phase11_features(raw)
            symbol_dataset = build_symbol_dataset(features, _asset_class(path), config)
            if not symbol_dataset.empty:
                datasets.append(symbol_dataset)
        except (KeyError, ValueError, OSError) as exc:
            failures.append({"path": str(path), "error": str(exc)})
    dataset = pd.concat(datasets, ignore_index=True) if datasets else pd.DataFrame()
    if not dataset.empty:
        dataset = dataset.sort_values(
            ["timestamp", "symbol", "holding_period"], kind="stable"
        ).reset_index(drop=True)
    audit = audit_dataset(dataset)
    audit_passed = bool(not audit.empty and audit["passed"].all())
    if audit_passed:
        dataset.to_parquet(config.dataset_path, index=False)

    artifacts: dict[str, str] = {}
    audit_path = config.output_root / "dataset_audit.csv"
    audit.to_csv(audit_path, index=False)
    artifacts["dataset_audit"] = str(audit_path)
    summary = _summary(dataset)
    summary_path = config.output_root / "dataset_summary.csv"
    summary.to_csv(summary_path, index=False)
    artifacts["dataset_summary"] = str(summary_path)
    label_summary = _label_summary(dataset)
    label_path = config.output_root / "label_summary.csv"
    label_summary.to_csv(label_path, index=False)
    artifacts["label_summary"] = str(label_path)
    schema = {
        "keys": ["timestamp", "symbol", "asset_class", "holding_period"],
        "features": list(FEATURE_COLUMNS),
        "labels": [
            "forward_return",
            "net_forward_return",
            "mfe",
            "mae",
            "positive_return_label",
            "risk_adjusted_label",
        ],
        "categorical_context": ["asset_class", "regime"],
    }
    artifacts["feature_schema"] = _write_json(schema, config.output_root / "feature_schema.json")
    artifacts["failures"] = _write_json(failures, config.output_root / "dataset_failures.json")
    manifest = {
        "phase": "11.0.0",
        "version": "0.11.0",
        "purpose": "point-in-time ML dataset construction",
        "config": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(config).items()
        },
        "scanned_files": len(files),
        "included_symbols": int(dataset["symbol"].nunique()) if not dataset.empty else 0,
        "rows": len(dataset),
        "audit_passed": audit_passed,
        "dataset_written": audit_passed,
    }
    artifacts["manifest"] = _write_json(manifest, config.output_root / "manifest.json")
    signoff = {
        "phase": "11.0.0",
        "status": "DATASET_READY" if audit_passed else "DATASET_BLOCKED",
        "audit_passed": audit_passed,
        "approved_for_model_training": audit_passed,
        "approved_for_paper_trading": False,
        "approved_for_live_trading": False,
    }
    artifacts["signoff"] = _write_json(signoff, config.output_root / "phase11_dataset_signoff.json")
    return Phase11Result(
        scanned_files=len(files),
        included_symbols=int(dataset["symbol"].nunique()) if not dataset.empty else 0,
        rows=len(dataset),
        output=str(config.output_root),
        dataset=str(config.dataset_path),
        audit_passed=audit_passed,
        artifacts=artifacts,
    )


def _summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            columns=["asset_class", "holding_period", "rows", "symbols", "start", "end"]
        )
    grouped = dataset.groupby(["asset_class", "holding_period"], observed=True)
    return grouped.agg(
        rows=("symbol", "size"),
        symbols=("symbol", "nunique"),
        start=("timestamp", "min"),
        end=("timestamp", "max"),
    ).reset_index()


def _label_summary(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(
            columns=[
                "asset_class",
                "holding_period",
                "rows",
                "positive_rate",
                "average_net_return",
                "average_mfe",
                "average_mae",
            ]
        )
    grouped = dataset.groupby(["asset_class", "holding_period"], observed=True)
    return grouped.agg(
        rows=("symbol", "size"),
        positive_rate=("positive_return_label", "mean"),
        average_net_return=("net_forward_return", "mean"),
        average_mfe=("mfe", "mean"),
        average_mae=("mae", "mean"),
    ).reset_index()
