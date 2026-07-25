Robinhood AI Quant — Final Phase 10.x package (v0.10.4)

What is included
- Phase 10.0 historical signal replay
- Phase 10.1 portfolio and fixed walk-forward analytics
- Phase 10.2 rolling validation, cost stress, benchmark comparison, leakage audit
- Phase 10.3 label quality, feature predictiveness, cross-sectional rank analysis
- Phase 10.4 time-decay, bootstrap confidence, final promotion gate and sign-off

Install/update
1. Back up your current project.
2. Replace the project files with this package, preserving your private .env and data directories.
3. Activate the Python 3.12 virtual environment.
4. Run:
   pip install -e ".[dev]"

Quality gate
   powershell -ExecutionPolicy Bypass -File .\scripts\phase10_smoke_test.ps1

Full replay
   python .\scripts\phase10_bundle.py --data-root .\data\validated --output .\reports\phase10_4_full

Validate an existing replay
   python .\scripts\phase10_4_validate.py ^
     --signal-replay .\reports\phase10_4_full\signal_replay.csv ^
     --output .\reports\phase10_4_validation

Final decision files
- reports\phase10_4_full\final_promotion_decisions.csv
- reports\phase10_4_full\phase10_final_signoff.json

Important
Phase 10.x completion does not authorize live trading. Only entries in
approved_for_phase11_paper_trading may proceed to paper execution validation.
