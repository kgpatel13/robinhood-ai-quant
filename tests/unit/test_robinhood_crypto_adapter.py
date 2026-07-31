from __future__ import annotations

from decimal import Decimal

import pytest

from src.brokers.errors import BrokerError, BrokerErrorCategory
from src.brokers.robinhood_crypto_adapter import RobinhoodCryptoReadOnlyAdapter
from src.execution.models import OrderRequest, OrderSide
from src.robinhood_crypto.models import BestBidAsk, CryptoAccount, CryptoHolding


class StubCryptoService:
    def get_account(self) -> CryptoAccount:
        return CryptoAccount("A1", "active", Decimal("100"), Decimal("80"))

    def list_holdings(self):
        return [CryptoHolding("BTC", Decimal("0.01"), Decimal("0.01"), Decimal("500"))]

    def get_best_bid_ask(self, symbols):
        assert symbols == ["BTC-USD"]
        return [BestBidAsk("BTC-USD", Decimal("60000"), Decimal("60200"), "now")]


def test_crypto_adapter_builds_account_and_marked_position() -> None:
    adapter = RobinhoodCryptoReadOnlyAdapter(StubCryptoService())  # type: ignore[arg-type]

    account = adapter.get_account()

    assert account.cash == 80.0
    assert account.buying_power == 80.0
    assert account.positions[0].symbol == "BTC-USD"
    assert account.positions[0].average_cost == 50000.0
    assert account.positions[0].market_price == 60100.0
    assert account.equity == 681.0


def test_crypto_adapter_blocks_live_mutation() -> None:
    adapter = RobinhoodCryptoReadOnlyAdapter(StubCryptoService())  # type: ignore[arg-type]

    with pytest.raises(BrokerError) as exc_info:
        adapter.submit_order(OrderRequest("BTC-USD", 0.001, OrderSide.BUY))

    assert exc_info.value.info.category is BrokerErrorCategory.SAFETY_BLOCK
