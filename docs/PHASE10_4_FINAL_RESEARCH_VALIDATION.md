# Phase 10.4 — Final Phase 10.x Research Validation

Phase 10.4 closes the historical research series. It adds independent diagnostics that
must agree with the rolling out-of-sample gate before a strategy can advance.

## New controls

- **Label quality:** MFE, MAE, capture efficiency, return-to-adverse-excursion, and tails.
- **Feature predictiveness:** Spearman information coefficient for point-in-time features.
- **Cross-sectional ranking:** verifies that higher same-date scores outperform lower ranks.
- **Time decay:** compares full-history performance with the latest three years.
- **Bootstrap confidence:** estimates the probability that mean return is genuinely positive.
- **Final promotion gate:** requires both Phase 10.2 and Phase 10.4 criteria.

## Promotion meaning

A passing result authorizes only Phase 11 paper-trading validation. It does not authorize
production or live-capital trading.
