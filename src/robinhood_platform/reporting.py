from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.robinhood_platform.models import (
    RobinhoodOperationalSnapshot,
    RobinhoodReadinessReport,
)


class RobinhoodReportWriter:
    @staticmethod
    def write_json(
        path: str | Path,
        *,
        readiness: RobinhoodReadinessReport,
        operations: RobinhoodOperationalSnapshot,
    ) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "readiness": asdict(readiness),
            "operations": asdict(operations),
        }
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        temporary.replace(output)
        return output
