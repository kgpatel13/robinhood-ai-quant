from __future__ import annotations

from typing import Any

import pytest

from src.robinhood_crypto.diagnostics import RobinhoodCryptoDiagnostics
from src.robinhood_crypto.endpoints import RobinhoodCryptoEndpoints
from src.robinhood_crypto.service import RobinhoodCryptoReadService


class FakeClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str | int | float] | None]] = []

    def get(
        self,
        path: str,
        *,
        params: dict[str, str | int | float] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((path, params))
        return self.responses[path]


def service(responses: dict[str, dict[str, Any]]) -> tuple[RobinhoodCryptoReadService, FakeClient]:
    client = FakeClient(responses)
    return RobinhoodCryptoReadService(client), client  # type: ignore[arg-type]


def test_get_account_parses_wrapped_result() -> None:
    api, _ = service(
        {
            RobinhoodCryptoEndpoints().account: {
                "results": [
                    {
                        "account_number": "secret",
                        "status": "active",
                        "buying_power": "100.00",
                        "crypto_buying_power": "75.00",
                    }
                ]
            }
        }
    )
    account = api.get_account()
    assert account.status == "active"
    assert str(account.crypto_buying_power) == "75.00"


def test_holdings_asset_filter_is_normalized() -> None:
    endpoint = RobinhoodCryptoEndpoints().holdings
    api, client = service({endpoint: {"results": []}})
    assert api.list_holdings(asset_code=" btc ") == []
    assert client.calls == [(endpoint, {"asset_code": "BTC"})]


def test_trading_pairs_symbol_normalization() -> None:
    endpoint = RobinhoodCryptoEndpoints().trading_pairs
    api, client = service({endpoint: {"results": []}})
    api.list_trading_pairs(symbols=["btc", "ETH-USD"])
    assert client.calls == [(endpoint, {"symbol": "BTC-USD,ETH-USD"})]


def test_best_bid_ask_parses_spread_prices() -> None:
    endpoint = RobinhoodCryptoEndpoints().best_bid_ask
    api, _ = service(
        {
            endpoint: {
                "results": [
                    {
                        "symbol": "BTC-USD",
                        "bid_inclusive_of_sell_spread": "60000.10",
                        "ask_inclusive_of_buy_spread": "60010.20",
                        "timestamp": "2026-07-30T22:00:00Z",
                    }
                ]
            }
        }
    )
    quote = api.get_best_bid_ask(["btc"])[0]
    assert str(quote.bid_price) == "60000.10"
    assert str(quote.ask_price) == "60010.20"


def test_estimated_price_validates_side() -> None:
    api, _ = service({})
    with pytest.raises(ValueError, match="side must"):
        api.get_estimated_price(symbol="BTC-USD", side="buy", quantity="0.01")


def test_estimated_price_parses_result() -> None:
    endpoint = RobinhoodCryptoEndpoints().estimated_price
    api, client = service(
        {
            endpoint: {
                "results": [
                    {
                        "quantity": "0.01",
                        "total_inclusive_of_spread": "600.00",
                        "estimated_unit_price": "60000.00",
                    }
                ]
            }
        }
    )
    estimate = api.get_estimated_price(symbol="btc", side="ask", quantity="0.01")
    assert estimate.symbol == "BTC-USD"
    assert str(estimate.total_notional) == "600.00"
    assert client.calls[0][1] == {
        "symbol": "BTC-USD",
        "side": "ask",
        "quantity": "0.01",
    }


def test_order_endpoint_rejects_path_injection() -> None:
    endpoints = RobinhoodCryptoEndpoints()
    with pytest.raises(ValueError, match="invalid URL"):
        endpoints.order("abc/../../secret")


def test_list_orders_is_read_only() -> None:
    endpoint = RobinhoodCryptoEndpoints().orders
    api, _ = service(
        {
            endpoint: {
                "results": [
                    {
                        "client_order_id": "order-1",
                        "symbol": "ETH-USD",
                        "side": "buy",
                        "type": "market",
                        "state": "filled",
                        "market_order_config": {"asset_quantity": "0.1"},
                        "average_price": "3000",
                    }
                ]
            }
        }
    )
    order = api.list_orders()[0]
    assert order.client_order_id == "order-1"
    assert str(order.quantity) == "0.1"


def test_diagnostics_omits_sensitive_values() -> None:
    endpoints = RobinhoodCryptoEndpoints()
    api, _ = service(
        {
            endpoints.account: {
                "results": [
                    {
                        "account_number": "do-not-return",
                        "status": "active",
                        "buying_power": "100",
                    }
                ]
            },
            endpoints.holdings: {"results": []},
            endpoints.trading_pairs: {"results": []},
            endpoints.best_bid_ask: {"results": []},
        }
    )
    result = RobinhoodCryptoDiagnostics(api).run(quote_symbols=["BTC-USD"])
    serialized = str(result)
    assert "do-not-return" not in serialized
    assert "100" not in serialized
    assert result["authenticated"] is True


def test_empty_quote_symbols_are_rejected() -> None:
    api, _ = service({})
    with pytest.raises(ValueError, match="at least one symbol"):
        api.get_best_bid_ask([])
