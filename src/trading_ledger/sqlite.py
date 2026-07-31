from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.execution.models import Fill, OrderRequest, OrderSide
from src.trading_ledger.models import LedgerPosition, LedgerSummary, utc_now


class SQLiteTradingLedger:
    """Durable SQLite event ledger for paper and shadow trading.

    The ledger is append-oriented. Portfolio state is reconstructed from fills, so a
    process restart does not lose cash, positions, cost basis, or realized P&L.
    """

    def __init__(self, path: Path, *, starting_cash: float = 100_000.0) -> None:
        if starting_cash <= 0:
            raise ValueError("starting_cash must be positive")
        self.path = path
        self.starting_cash = float(starting_cash)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS ledger_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    client_order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    limit_price REAL,
                    status TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    commission REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(order_id)
                );

                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cash REAL NOT NULL,
                    equity REAL NOT NULL,
                    buying_power REAL NOT NULL,
                    positions_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
                CREATE INDEX IF NOT EXISTS idx_fills_symbol_time ON fills(symbol, timestamp);
                CREATE INDEX IF NOT EXISTS idx_risk_events_time ON risk_events(recorded_at);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO ledger_meta(key, value) VALUES('starting_cash', ?)",
                (repr(self.starting_cash),),
            )
            row = connection.execute(
                "SELECT value FROM ledger_meta WHERE key='starting_cash'"
            ).fetchone()
            if row is not None:
                self.starting_cash = float(row["value"])

    def record_order(
        self,
        *,
        order_id: str,
        request: OrderRequest,
        status: str,
        strategy: str = "unknown",
        message: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        now = (timestamp or utc_now()).astimezone(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO orders(
                    order_id, client_order_id, symbol, side, order_type, quantity,
                    limit_price, status, strategy, created_at, updated_at, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    message=excluded.message
                """,
                (
                    order_id,
                    request.client_order_id,
                    request.symbol,
                    request.side.value,
                    request.order_type.value,
                    request.quantity,
                    request.limit_price,
                    status,
                    strategy,
                    now,
                    now,
                    message,
                ),
            )

    def record_fill(self, fill: Fill) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO fills(
                    fill_id, order_id, symbol, side, quantity, price, commission, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fill.fill_id,
                    fill.order_id,
                    fill.symbol,
                    fill.side.value,
                    fill.quantity,
                    fill.price,
                    fill.commission,
                    fill.timestamp.astimezone(UTC).isoformat(),
                ),
            )

    def record_account_snapshot(
        self,
        *,
        cash: float,
        equity: float,
        buying_power: float,
        positions: list[Mapping[str, Any]],
        timestamp: datetime | None = None,
    ) -> None:
        recorded_at = (timestamp or utc_now()).astimezone(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO account_snapshots(
                    cash, equity, buying_power, positions_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (cash, equity, buying_power, json.dumps(positions, sort_keys=True), recorded_at),
            )

    def record_risk_event(
        self,
        *,
        code: str,
        severity: str,
        message: str,
        context: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        recorded_at = (timestamp or utc_now()).astimezone(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO risk_events(code, severity, message, context_json, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    code,
                    severity,
                    message,
                    json.dumps(dict(context or {}), sort_keys=True),
                    recorded_at,
                ),
            )

    def positions(
        self, market_prices: Mapping[str, float] | None = None
    ) -> tuple[LedgerPosition, ...]:
        prices = {symbol.upper(): float(price) for symbol, price in (market_prices or {}).items()}
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT symbol, side, quantity, price FROM fills ORDER BY timestamp, fill_id"
            ).fetchall()

        state: dict[str, tuple[float, float]] = {}
        for row in rows:
            symbol = str(row["symbol"]).upper()
            side = OrderSide(str(row["side"]))
            quantity = float(row["quantity"])
            price = float(row["price"])
            current_quantity, average_cost = state.get(symbol, (0.0, 0.0))
            if side is OrderSide.BUY:
                new_quantity = current_quantity + quantity
                new_cost = current_quantity * average_cost + quantity * price
                state[symbol] = (new_quantity, new_cost / new_quantity)
            else:
                if quantity > current_quantity + 1e-12:
                    raise ValueError(f"ledger contains oversold position for {symbol}")
                new_quantity = current_quantity - quantity
                state[symbol] = (
                    (0.0, 0.0) if new_quantity <= 1e-12 else (new_quantity, average_cost)
                )

        result: list[LedgerPosition] = []
        for symbol, (quantity, average_cost) in sorted(state.items()):
            if quantity <= 1e-12:
                continue
            result.append(
                LedgerPosition(
                    symbol=symbol,
                    quantity=quantity,
                    average_cost=average_cost,
                    market_price=prices.get(symbol, average_cost),
                )
            )
        return tuple(result)

    def summary(self, market_prices: Mapping[str, float] | None = None) -> LedgerSummary:
        positions = self.positions(market_prices)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT side, quantity, price, commission FROM fills ORDER BY timestamp, fill_id"
            ).fetchall()
            order_count = int(connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
            fill_count = len(rows)

        cash = self.starting_cash
        realized_pnl = 0.0
        inventory: dict[str, tuple[float, float]] = {}
        with self._connection() as connection:
            detailed = connection.execute(
                "SELECT symbol, side, quantity, price, commission "
                "FROM fills ORDER BY timestamp, fill_id"
            ).fetchall()
        for row in detailed:
            symbol = str(row["symbol"]).upper()
            side = OrderSide(str(row["side"]))
            quantity = float(row["quantity"])
            price = float(row["price"])
            commission = float(row["commission"])
            current_quantity, average_cost = inventory.get(symbol, (0.0, 0.0))
            if side is OrderSide.BUY:
                cash -= quantity * price + commission
                new_quantity = current_quantity + quantity
                new_cost = current_quantity * average_cost + quantity * price
                inventory[symbol] = (new_quantity, new_cost / new_quantity)
            else:
                cash += quantity * price - commission
                realized_pnl += quantity * (price - average_cost) - commission
                remaining = current_quantity - quantity
                inventory[symbol] = (0.0, 0.0) if remaining <= 1e-12 else (remaining, average_cost)

        market_value = sum(position.market_value for position in positions)
        unrealized_pnl = sum(position.unrealized_pnl for position in positions)
        return LedgerSummary(
            starting_cash=self.starting_cash,
            cash=cash,
            market_value=market_value,
            equity=cash + market_value,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            order_count=order_count,
            fill_count=fill_count,
            as_of=utc_now(),
        )
