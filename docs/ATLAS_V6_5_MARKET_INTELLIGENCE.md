# Atlas v6.5 Market Intelligence Platform

Atlas v6.5 adds a cohesive market-context layer without removing or replacing any existing
package. It converts market regime, cross-asset behavior, volatility, sector leadership, and
scheduled event risk into a deterministic intelligence snapshot suitable for research, paper
trading, portfolio sizing, and later multi-agent decision workflows.

## Components

- Cross-asset risk-on, neutral, risk-off, and stress assessment
- Existing regime-intelligence integration
- EWMA volatility forecasting and volatility-expansion detection
- Sector relative-strength and risk-adjusted momentum ranking
- Macro, earnings, corporate-action, holiday, and crypto-network event windows
- Event-aware trade blocking and size reduction
- Strategy-category recommendations
- Unified size multiplier and explainable reasons

## Safety

The package does not fetch external data, store credentials, or submit orders. Callers provide
normalized observations. Critical event windows and stress conditions can reduce the recommended
size multiplier to zero. Live trading remains disabled by the existing execution safety controls.
