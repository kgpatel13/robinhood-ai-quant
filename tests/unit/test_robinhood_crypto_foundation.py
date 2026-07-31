from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from src.robinhood_crypto.client import RobinhoodCryptoClient, RobinhoodCryptoClientConfig
from src.robinhood_crypto.credentials import RobinhoodCryptoCredentialManager
from src.robinhood_crypto.signing import RobinhoodCryptoSigner

PRIVATE_KEY = "xQnTJVeQLmw1/Mg2YimEViSpw/SdJcgNXZ5kQkAXNPU="
API_KEY = "rh-api-6148effc-c0b1-486c-8940-a1d099456be6"
EXPECTED_SIGNATURE = (
    "6tIj8o6p+4w+ZnaxVanHtxjhC6s5z4lTI+8lNRjJOZp0dVDlco2NR6obVwBiECP8eoHtfcbsGfTu1rESBHOzCA=="
)


def test_signature_is_deterministic_for_documented_credentials() -> None:
    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    signer = RobinhoodCryptoSigner(credentials)
    body = json.dumps(
        {
            "client_order_id": "131de903-5a9c-4260-abc1-28d562a5dcf0",
            "side": "buy",
            "type": "market",
            "symbol": "BTC-USD",
            "market_order_config": {"asset_quantity": "0.1"},
        },
        separators=(",", ":"),
    )

    headers = signer.sign(
        method="POST",
        path="/api/v1/crypto/trading/orders/",
        body=body,
        timestamp=1698708981,
    )

    assert headers.signature == EXPECTED_SIGNATURE
    assert headers.as_dict()["x-timestamp"] == "1698708981"


def test_credential_manager_reads_private_key_file(tmp_path: Path) -> None:
    key_file = tmp_path / "crypto.key"
    key_file.write_text(f" {PRIVATE_KEY}\n", encoding="utf-8")
    manager = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY_PATH": str(key_file),
        }
    )

    assert manager.available()
    assert manager.resolve().private_key_base64 == PRIVATE_KEY


def test_credential_manager_rejects_ambiguous_private_key_sources() -> None:
    manager = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY_PATH": "secret.key",
        }
    )

    assert not manager.available()
    with pytest.raises(RuntimeError, match="exactly one"):
        manager.resolve()


class _FakeResponse:
    ok = True
    status_code = 200
    reason = "OK"
    text = ""

    def json(self) -> dict[str, Any]:
        return {"ok": True}


class _FakeSession(requests.Session):
    def __init__(self) -> None:
        super().__init__()
        self.last_request: dict[str, Any] = {}

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.last_request = {"method": method, "url": url, **kwargs}
        return _FakeResponse()


def test_client_signs_query_string_and_sends_read_only_request() -> None:
    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    session = _FakeSession()
    client = RobinhoodCryptoClient(
        RobinhoodCryptoSigner(credentials, clock=lambda: 123.0),
        session=session,
    )

    assert client.get("/api/v1/crypto/marketdata/best_bid_ask/", params={"symbol": "BTC-USD"}) == {
        "ok": True
    }
    headers = session.last_request["headers"]
    assert headers["x-api-key"] == API_KEY
    assert headers["x-timestamp"] == "123"
    assert headers["x-signature"]


def test_client_blocks_mutating_request_by_default() -> None:
    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    client = RobinhoodCryptoClient(RobinhoodCryptoSigner(credentials))

    with pytest.raises(RuntimeError, match="mutating requests are disabled"):
        client.request(
            "POST",
            "/api/v1/crypto/trading/orders/",
            payload={"symbol": "BTC-USD"},
            mutating=True,
        )


def test_client_requires_explicit_mutating_enablement() -> None:
    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    session = _FakeSession()
    client = RobinhoodCryptoClient(
        RobinhoodCryptoSigner(credentials, clock=lambda: 123.0),
        config=RobinhoodCryptoClientConfig(order_submission_enabled=True),
        session=session,
    )

    result = client.request(
        "POST",
        "/api/v1/crypto/trading/orders/",
        payload={"symbol": "BTC-USD"},
        mutating=True,
    )

    assert result == {"ok": True}
    assert session.last_request["data"] == '{"symbol":"BTC-USD"}'


def test_client_encodes_repeated_symbol_parameters_in_signature_and_request() -> None:
    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    session = _FakeSession()
    client = RobinhoodCryptoClient(
        RobinhoodCryptoSigner(credentials, clock=lambda: 123.0),
        session=session,
    )

    client.get(
        "/api/v1/crypto/trading/trading_pairs/",
        params=[("symbol", "BTC-USD"), ("symbol", "ETH-USD")],
    )

    assert session.last_request["params"] == [
        ("symbol", "BTC-USD"),
        ("symbol", "ETH-USD"),
    ]


def test_client_follows_same_host_pagination() -> None:
    class PaginatedSession(_FakeSession):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[dict[str, Any]] = []

        def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
            self.requests.append({"method": method, "url": url, **kwargs})
            page = len(self.requests)
            response = _FakeResponse()
            response.json = lambda: (  # type: ignore[method-assign]
                {
                    "results": [{"page": 1}],
                    "next": "https://trading.robinhood.com/api/v1/items/?cursor=abc",
                }
                if page == 1
                else {"results": [{"page": 2}], "next": None}
            )
            return response

    credentials = RobinhoodCryptoCredentialManager(
        environment={
            "ROBINHOOD_CRYPTO_API_KEY": API_KEY,
            "ROBINHOOD_CRYPTO_PRIVATE_KEY": PRIVATE_KEY,
        }
    ).resolve()
    session = PaginatedSession()
    client = RobinhoodCryptoClient(
        RobinhoodCryptoSigner(credentials, clock=lambda: 123.0), session=session
    )

    pages = client.get_pages("/api/v1/items/", params={"limit": 1})

    assert len(pages) == 2
    assert session.requests[1]["params"] == [("cursor", "abc")]
