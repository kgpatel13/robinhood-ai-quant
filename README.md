# Robinhood AI Quant — Phase 1 Foundation

This repository is the Phase 1 engineering foundation for a broker-independent,
AI-assisted quantitative trading platform.

## Safety boundary

This phase:

- does not connect to Robinhood;
- contains no broker credentials;
- cannot place live orders;
- contains no options, leverage, margin, or short-selling logic;
- focuses on project structure, configuration, testing, logging, and reproducibility.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.11 or 3.12
- Git
- VS Code recommended

## Windows PowerShell setup

```powershell
cd robinhood-ai-quant-phase1
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\.venv\Scripts\Activate.ps1
python -m src.main healthcheck
python -m src.main config-validate
pytest
```

## Windows Command Prompt setup

```bat
cd robinhood-ai-quant-phase1
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m src.main healthcheck
python -m src.main config-validate
pytest
```

## macOS/Linux setup

```bash
cd robinhood-ai-quant-phase1
chmod +x scripts/setup.sh
./scripts/setup.sh
source .venv/bin/activate
```

## Quality checks

```bash
python -m src.main healthcheck
python -m src.main config-validate
pytest
ruff check .
ruff format --check .
mypy src
```

## Phase 1 completion criteria

1. Environment installs successfully.
2. Health check passes.
3. Configuration validation passes.
4. Tests pass.
5. Ruff and mypy pass.
6. GitHub Actions passes after pushing to a private repository.
7. No credentials or secrets are committed.

## Next phase

Phase 2 adds historical market-data ingestion, normalization, validation,
caching, and initial research datasets.
