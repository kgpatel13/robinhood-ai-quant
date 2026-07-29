Atlas v9.0.0 Ruff/MyPy compatibility fix

Replace the included src folders/files in the project root, preserving paths.

Fixes:
- UP035 Mapping imports moved to collections.abc
- F401 unused AgentOpinion and AgentRole imports removed
- UP040 aliases converted to Python 3.12 type statements
- MyPy AgentAction dictionary key inference fixed with explicit annotation

Then run:
python -m ruff check src tests scripts
python -m mypy src
python -m pytest
