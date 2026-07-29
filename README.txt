Atlas v9.0.0 cleanup fix

1. Extract this ZIP directly into C:\Projects\robinhood-ai-quant.
2. From the project root run:
   .\APPLY_FIX.ps1
3. Then run Ruff, MyPy, and PyTest.

The script removes only the accidental src\src duplicate folder and copies the corrected files into the real src folder.
