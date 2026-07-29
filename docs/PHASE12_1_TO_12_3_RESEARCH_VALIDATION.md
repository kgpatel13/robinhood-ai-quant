# Phase 12.1–12.3: Institutional Research Validation

This release adds three connected safeguards between model training and paper deployment.

## 12.1 Probability calibration

`ProbabilityCalibrator` supports sigmoid and isotonic calibration, plus Brier score, log loss, expected calibration error, and maximum calibration error.

## 12.2 Walk-forward evaluation

`WalkForwardEvaluator` performs chronological expanding- or rolling-window evaluation without training on future observations.

## 12.3 Bootstrap robustness

`TradeReturnBootstrap` uses deterministic IID or block bootstrap simulations to estimate confidence intervals and the probability that a strategy remains profitable.

These components are research-only. They do not enable broker execution.
