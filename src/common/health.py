from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from src.common.config import AppSettings


def collect_health(settings: AppSettings) -> dict[str, Any]:
    required = [
        settings.config_dir,
        settings.data_dir,
        settings.reports_dir,
        settings.logs_dir,
    ]
    return {
        "application": "robinhood-ai-quant",
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "working_directory": str(Path.cwd()),
        "environment": settings.app_env,
        "directories": {str(path): path.exists() for path in required},
        "live_trading_capability": False,
    }
