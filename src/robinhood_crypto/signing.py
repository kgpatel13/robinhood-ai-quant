from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from time import time
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.robinhood_crypto.credentials import RobinhoodCryptoCredentials


class Clock(Protocol):
    def __call__(self) -> float: ...


@dataclass(frozen=True, slots=True)
class SignedHeaders:
    api_key: str
    timestamp: int
    signature: str

    def as_dict(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "x-signature": self.signature,
            "x-timestamp": str(self.timestamp),
        }


class RobinhoodCryptoSigner:
    """Creates Robinhood Crypto Ed25519 authentication headers."""

    def __init__(
        self,
        credentials: RobinhoodCryptoCredentials,
        *,
        clock: Clock = time,
    ) -> None:
        self._credentials = credentials
        self._clock = clock
        self._signing_key = self._decode_signing_key(credentials.private_key_base64)

    def sign(
        self,
        *,
        method: str,
        path: str,
        body: str = "",
        timestamp: int | None = None,
    ) -> SignedHeaders:
        normalized_method = method.strip().upper()
        normalized_path = path.strip()
        if not normalized_method:
            raise ValueError("HTTP method is required")
        if not normalized_path.startswith("/"):
            raise ValueError("request path must start with '/'")

        current_timestamp = int(self._clock()) if timestamp is None else timestamp
        if current_timestamp < 0:
            raise ValueError("timestamp cannot be negative")

        message = (
            f"{self._credentials.api_key}{current_timestamp}"
            f"{normalized_path}{normalized_method}{body}"
        )
        raw_signature = self._signing_key.sign(message.encode("utf-8"))
        signature = base64.b64encode(raw_signature).decode("ascii")
        return SignedHeaders(
            api_key=self._credentials.api_key,
            timestamp=current_timestamp,
            signature=signature,
        )

    @staticmethod
    def _decode_signing_key(private_key_base64: str) -> Ed25519PrivateKey:
        try:
            raw_key = base64.b64decode(private_key_base64.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Robinhood Crypto private key is not valid base64") from exc
        if len(raw_key) != 32:
            raise ValueError("Robinhood Crypto private key must be a 32-byte Ed25519 seed")
        return Ed25519PrivateKey.from_private_bytes(raw_key)
