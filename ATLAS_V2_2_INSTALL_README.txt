Atlas AI v2.2.0 - Market Intelligence Foundation

INSTALL
1. Back up or commit the current main branch.
2. Extract this ZIP into the repository root and allow files to merge/replace.
3. Reinstall editable dependencies so the new atlas-market console command is registered:
   pip install -e ".[dev]"
4. Validate:
   ruff check .
   mypy .
   pytest

RUN
python scripts\atlas_v2_2_market_intelligence.py

INPUT FORMAT
Place one daily OHLCV CSV per asset in data/market/daily.
Filename convention:
  stock:AAPL   -> stock__AAPL.csv
  crypto:bitcoin -> crypto__bitcoin.csv

Required columns:
  timestamp,open,high,low,close,volume

The v2.2 runner safely skips registry assets for which no history file exists.
It does not place trades and does not enable paper or live execution.

OUTPUTS
- data/market/features.csv
- reports/atlas_v2/market_snapshot.json
- reports/atlas_v2/market_intelligence.json

IMPLEMENTED
- Deterministic OHLCV validation
- SMA 20 / SMA 50 / EMA 20
- ATR 14 / RSI 14
- 1d / 5d / 20d return
- 20d annualized volatility
- relative volume
- distance from 20d high
- liquidity score
- data-quality score
- composite market-quality score
- market-regime classification
- atomic feature/report writes

VALIDATION IN BUILD ENVIRONMENT
- Python compilation: PASS
- Focused Atlas test suite: 12 PASS
- Run Ruff, MyPy, and the complete project test suite in the repository virtual environment.
