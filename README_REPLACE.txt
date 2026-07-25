Phase 15.0.1 quality patch

Replace these files in C:\Projects\robinhood-ai-quant:

1. src\research\phase15\engine.py
2. scripts\phase15_smoke_test.ps1

The engine replacement fixes:
- Ruff unused imports
- MyPy numeric product inference
- MyPy champion-selection key typing
- MyPy pandas.cut overload typing
- the accidental champion_counts NameError in threshold economics

The PowerShell smoke-test replacement now stops immediately when any external
command returns a non-zero exit code. It will no longer print a false success
message after Ruff, MyPy, or PyTest fails.
