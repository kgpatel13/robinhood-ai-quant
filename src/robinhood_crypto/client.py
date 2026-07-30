from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from src.robinhood_crypto.signing import RobinhoodCryptoSigner


@dataclass(frozen=True, slots=True)
class RobinhoodCryptoClientConfig:
    base_url: str = "https://trading.robinhood.com"
    timeout_seconds: float = 10.0
    order_submission_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("Robinhood Crypto base_url must use HTTPS")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class RobinhoodCryptoClient:
    """Minimal signed HTTP transport with fail-closed order submission."""

    def __init__(
        self,
        signer: RobinhoodCryptoSigner,
        *,
        config: RobinhoodCryptoClientConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._signer = signer
        self._config = config or RobinhoodCryptoClientConfig()
        self._session = session or requests.Session()

    def get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
    ) -> dict[str, Any]:
        return self.request("GET", path, params=params)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | float] | None = None,
        payload: Mapping[str, Any] | None = None,
        mutating: bool = False,
    ) -> dict[str, Any]:
        normalized_method = method.strip().upper()
        if mutating and not self._config.order_submission_enabled:
            raise RuntimeError("Robinhood Crypto mutating requests are disabled")
        if payload is not None and normalized_method in {"GET", "HEAD"}:
            raise ValueError(f"{normalized_method} requests cannot include a JSON payload")

        query = urlencode(params or {}, doseq=False)
        signed_path = f"{path}?{query}" if query else path
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
        signed_headers = self._signer.sign(
            method=normalized_method,
            path=signed_path,
            body=body,
        )
        headers = {
            **signed_headers.as_dict(),
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"

        response = self._session.request(
            normalized_method,
            f"{self._config.base_url.rstrip('/')}{path}",
            params=dict(params or {}),
            data=body or None,
            headers=headers,
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Robinhood Crypto response must be a JSON object")
        return data
