# Atlas v4.6.3 — Phase 16.1–16.3 Portfolio Intelligence

This release adds portfolio-level construction and allocation controls between strategy
approval and paper execution.

## Phase 16.1 — Portfolio Optimizer

`src.portfolio_optimizer` supports long-only minimum-variance, equal-risk-contribution
(risk parity), and maximum-diversification objectives. Explicit minimum/maximum position
weights and a reserved cash weight are enforced during optimization.

## Phase 16.2 — Dynamic Capital Allocation

`src.capital_allocator` supports fixed-fractional, fractional-Kelly, and volatility-target
sizing. Confidence, drawdown, maximum allocation, and daily risk-budget controls are
applied before capital is approved.

## Phase 16.3 — Correlation and Diversification Engine

`src.correlation_engine` computes rolling correlations, hierarchical correlation clusters,
high-correlation pairs, cluster exposure, sector exposure, concentration warnings, and a
portfolio diversification score.

All functionality is research and paper-trading infrastructure. This release does not
enable live order submission.
