from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.atlas.models import AtlasConfig, ExperimentManifest


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def optional_file_sha256(path: Path) -> str | None:
    return file_sha256(path) if path.exists() and path.is_file() else None


def git_state(project_root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", False


def build_experiment_id(config: AtlasConfig, input_fingerprints: dict[str, str]) -> str:
    stable = {
        "config": asdict(config),
        "inputs": input_fingerprints,
        "seed": config.random_seed,
    }
    return f"atlas-{canonical_json_sha256(stable)[:16]}"


def create_manifest(
    *,
    project_root: Path,
    platform_version: str,
    config: AtlasConfig,
    input_fingerprints: dict[str, str],
    artifacts: dict[str, str],
) -> ExperimentManifest:
    commit, dirty = git_state(project_root)
    experiment_id = build_experiment_id(config, input_fingerprints)
    return ExperimentManifest(
        experiment_id=experiment_id,
        created_at_utc=datetime.now(UTC).isoformat(),
        platform_version=platform_version,
        git_commit=commit,
        git_dirty=dirty,
        random_seed=config.random_seed,
        config_sha256=canonical_json_sha256(asdict(config)),
        input_fingerprints=input_fingerprints,
        baseline_fingerprint=optional_file_sha256(config.baseline_signoff),
        artifacts=artifacts,
    )
