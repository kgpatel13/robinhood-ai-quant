# Phase 21.1-21.3: AI Research Assistant

Atlas v5.1.3 adds a safe, auditable research coordination layer.

## Phase 21.1 — Research planning

Structured research requests are converted into explicit workflows, required evidence, and safety
requirements. The planner requires point-in-time data, out-of-sample validation, and manual approval.

## Phase 21.2 — Candidate evaluation

Candidate evidence is scored and classified as `recommend`, `review`, or `reject` using deterministic
constraints for Sharpe ratio, drawdown, trade count, regime coverage, stability, slippage, and
out-of-sample status.

## Phase 21.3 — Recommendation reports

The assistant ranks candidates and writes machine-readable JSON plus a concise Markdown report. It
never submits broker orders and does not bypass promotion governance.
