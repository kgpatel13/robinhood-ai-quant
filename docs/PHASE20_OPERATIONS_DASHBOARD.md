# Phase 20.1–20.3 — Operations Dashboard, Alerting, and Auditability

Atlas v5.0.3 introduces a read-only operations control plane for paper and future live
execution workflows.

## Phase 20.1 — Operations snapshot service

`src.operations_dashboard` aggregates execution metrics, production safety,
reconciliation, component health, and model-health summaries into a stable UI-ready
snapshot. The service reports `operational`, `degraded`, or `halted` and never bypasses
an existing safety or reconciliation decision.

## Phase 20.2 — Alerting

`src.alerting` provides typed alert rules for platform halts, elevated order rejection
rates, and model drift. Alerts include deterministic rule identifiers and cooldown-based
deduplication to prevent repeated notification storms.

## Phase 20.3 — Audit log and Streamlit console

`src.audit_log` provides an append-only JSONL event store with flush and fsync durability.
`dashboard/operations_console.py` is a read-only Streamlit operations view. It does not
enable live trading or hold broker credentials.

## Safety

Live execution remains disabled by default. The dashboard represents state; it does not
override production safety, broker reconciliation, or execution policy gates.
