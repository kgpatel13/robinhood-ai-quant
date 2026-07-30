from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RobinhoodCryptoEndpoints:
    account: str = "/api/v1/crypto/trading/accounts/"
    holdings: str = "/api/v1/crypto/trading/holdings/"
    trading_pairs: str = "/api/v1/crypto/trading/trading_pairs/"
    best_bid_ask: str = "/api/v1/crypto/marketdata/best_bid_ask/"
    estimated_price: str = "/api/v1/crypto/marketdata/estimated_price/"
    orders: str = "/api/v1/crypto/trading/orders/"

    def order(self, client_order_id: str) -> str:
        normalized = client_order_id.strip()
        if not normalized:
            raise ValueError("client_order_id is required")
        if "/" in normalized or "?" in normalized or "#" in normalized:
            raise ValueError("client_order_id contains invalid URL characters")
        return f"{self.orders}{normalized}/"
