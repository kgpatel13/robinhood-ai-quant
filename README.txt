Atlas Phase 4.4 optimizer console/type-check fix

Replace these files in C:\Projects\robinhood-ai-quant:
  src\atlas\portfolio\optimizer.py
  scripts\atlas_v4_optimizer.py

Then run:
  python -m ruff check src tests scripts
  python -m mypy src
  python -m pytest
  python -m scripts.atlas_v4_optimizer --capital 100000
