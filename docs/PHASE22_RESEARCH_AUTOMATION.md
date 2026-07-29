# Phase 22.1–22.3 — Research Automation and Reproducibility

Atlas v5.2.3 adds an auditable automation layer around the AI research assistant.

## Phase 22.1 — Automated research runs

`ResearchAutomationPipeline` coordinates planning, candidate evaluation, ranking, and a
non-executing promotion recommendation. It records created, running, completed, and failed
states.

## Phase 22.2 — Reproducibility and experiment catalog

Every request receives a deterministic SHA-256 fingerprint. `ResearchRunCatalog` persists the
full lifecycle as append-only JSONL with flush and filesystem synchronization.

## Phase 22.3 — Controlled promotion recommendations

The pipeline can recommend no action, shadow, paper, or manual review. Manual review remains the
default. The package has no broker dependency and cannot submit orders.
