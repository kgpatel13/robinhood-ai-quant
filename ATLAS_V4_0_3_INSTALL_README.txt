Atlas v4.0.3 — Phase 10.1–10.3 Broker Abstraction Foundation

1. Back up your current project folder.
2. Extract this archive over C:\Projects\robinhood-ai-quant.
3. Allow replacement of existing files.
4. Activate the virtual environment.
5. Run:

python -m pip install -e ".[dev,dashboard]"
python -m ruff format .
python -m ruff check . --fix
python -m mypy .
python -m pytest

Safety status: PAPER ONLY. Live broker routing remains disabled.
