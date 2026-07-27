Atlas Phase 4.7 Static Analysis Replacement Fix

Replace:
  src\atlas\portfolio\execution.py

Fixes:
- Ruff UP035: Mapping and Sequence imported from collections.abc
- Ruff E501: long warning string wrapped below 100 characters

No execution-model behavior or report calculations are changed.
