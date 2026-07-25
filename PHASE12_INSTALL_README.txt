Phase 12.0-12.9 installation

1. Extract this ZIP over the project root.
2. Activate the existing virtual environment.
3. Run: pip install -e ".[dev]"
4. Run: python -m ruff format .
5. Run: powershell -ExecutionPolicy Bypass -File .\scripts\phase12_smoke_test.ps1
6. Run the production command documented in docs\PHASE12_RESEARCH_VALIDATION.md.
7. Zip and share reports\phase12_research_validation for review.
