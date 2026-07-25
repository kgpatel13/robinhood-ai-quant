PHASE 15.0-15.9 — AI ALPHA ENGINE
Version: 0.15.0

Capabilities
- Leakage-safe expanding walk-forward meta-labeling
- Champion/challenger model tournament
- Logistic, Random Forest, Extra Trees, and Histogram Gradient Boosting models
- Chronological model selection using validation data only
- Out-of-sample probability scoring and calibration diagnostics
- Adaptive threshold economics
- Asset-class, symbol, and market-regime policy reports
- Feature-importance explainability
- Serialized champion model
- Phase 16 promotion gate
- Paper and live trading remain disabled

Run
python .\scripts\phase15_alpha_engine.py `
  --trades .\reports\phase12_research_validation\simulated_trades.csv `
  --output .\reports\phase15_alpha_engine

Quality gate
powershell -ExecutionPolicy Bypass -File .\scripts\phase15_smoke_test.ps1
