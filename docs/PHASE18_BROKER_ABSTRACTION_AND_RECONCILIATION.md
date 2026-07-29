# Phase 18.1-18.3: Broker Abstraction and Reconciliation

Atlas v4.8.3 extends the existing audited paper-broker boundary into a broker-neutral
operational layer.

## Phase 18.1

- Expanded `BrokerAdapter` protocol with connection, health, position, and replacement APIs.
- Added normalized broker health models and a named adapter registry.
- Preserved the existing execution models as the canonical Atlas order/account vocabulary.

## Phase 18.2

- Added an injected `BrokerTransport` boundary for official SDK or HTTP implementations.
- Added guarded Alpaca and Robinhood adapters.
- Kept credentials and authentication outside source code.
- Kept live routing disabled unless both the adapter mode and safety policy explicitly permit it.
- Continued using the deterministic paper broker as the reference implementation.

## Phase 18.3

- Added account, position, order, status, and duplicate-client-ID reconciliation.
- Added policy-controlled `MATCHED`, `WARNING`, and `HALT` decisions.
- Added atomic JSON checkpoints for restart recovery.

No broker credentials are included. No live trading is enabled by this release.
