# Project Charter

## Mission

Build a robust, broker-independent, AI-assisted quantitative trading platform
that seeks to improve after-cost, after-tax, risk-adjusted returns while
operating within strict predefined risk limits.

## Phase 1 scope

- Repository and Python package structure
- Configuration management
- Secure environment-variable handling
- Logging
- Automated tests
- Linting and static type checking
- Continuous integration
- Documentation

## Phase 1 exclusions

- Robinhood connectivity
- Credentials
- Live orders
- Market-data downloads
- Strategy execution
- AI models
- Portfolio optimization

## Non-negotiable rules

- No live-order capability in Phase 1.
- No secrets in source control.
- AI may never override hard-coded risk policy.
- No options, margin, leverage, short selling, or martingale.
- Future decisions must be auditable.
