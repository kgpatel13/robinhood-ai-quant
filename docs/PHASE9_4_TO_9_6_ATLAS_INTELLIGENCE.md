# Phase 9.4–9.6 — Atlas Intelligence

This release adds three local, auditable intelligence services.

## Multi-timeframe intelligence

`MultiTimeframeAnalyzer` combines independently prepared monthly, weekly, daily, hourly, and intraday OHLCV frames. It reports aggregate direction, confirmation, conflict, entry quality, reasons, and whether a trade is allowed.

## Explainable decisions

`TradeExplanationBuilder` converts multi-timeframe, regime, model, and risk evidence into a deterministic explanation. `ExplanationJournal` persists JSONL records for later audit and dashboard use.

## Atlas Assistant

`AtlasAssistant` provides a deterministic local query layer for positions, losing positions, performance, weak strategies, and saved explanations. It has no external LLM or network dependency.

Live broker submission remains disabled.
