# Atlas v7.5 to v9.0 Combined Milestone

This release adds three connected platform layers while preserving all prior source files.

## Atlas v7.5 — Multi-Agent AI

Provides typed research, strategy, portfolio, risk, market, execution, and supervisor roles.
The supervisor fuses weighted opinions, applies risk and execution vetoes, limits position size,
and records an explainable decision trail. Agent implementations remain deterministic by default;
external LLM-backed agents can implement the same `DecisionAgent` interface later.

## Atlas v8.0 — Live Production Platform

Provides credential references resolved from environment variables, deployment stages, canary
capital limits, service-health gates, reconciliation gates, a thread-safe kill switch, and atomic
restart checkpoints. Live trading is not enabled automatically. A deployment policy must explicitly
select canary or production and every safety gate must pass.

## Atlas v9.0 — Self-Improving AI

Provides evidence-based strategy lifecycle management, automatic strategy retirement, bounded
adaptive weighting, feature selection with stability and redundancy checks, adaptive parameter
search, and a safeguarded bandit-style policy updater. Policy updates are bounded, risk-penalized,
and normalized. This is not unrestricted online reinforcement learning.

## Safety boundary

Research and learning outputs remain recommendations until promotion governance, production
safety, reconciliation, broker capabilities, and execution risk controls independently approve them.
