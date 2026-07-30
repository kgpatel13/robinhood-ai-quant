from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RobinhoodCryptoCredentialRefs:
    """Environment-variable references for Robinhood Crypto credentials.

    The private key may be provided directly as a base64 value or indirectly
    through a file path. Supplying both is rejected to avoid ambiguity.
    """

    api_key_env: str = "ROBINHOOD_CRYPTO_API_KEY"
    private_key_env: str = "ROBINHOOD_CRYPTO_PRIVATE_KEY"
    private_key_path_env: str = "ROBINHOOD_CRYPTO_PRIVATE_KEY_PATH"

    def __post_init__(self) -> None:
        names = (self.api_key_env, self.private_key_env, self.private_key_path_env)
        if any(not name.strip() for name in names):
            raise ValueError("credential environment-variable names are required")


@dataclass(frozen=True, slots=True)
class RobinhoodCryptoCredentials:
    api_key: str
    private_key_base64: str

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("Robinhood Crypto API key is required")
        if not self.private_key_base64.strip():
            raise ValueError("Robinhood Crypto private key is required")


class RobinhoodCryptoCredentialManager:
    """Loads credentials without logging or persisting secret values."""

    def __init__(
        self,
        refs: RobinhoodCryptoCredentialRefs | None = None,
        *,
        environment: Mapping[str, str] | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._refs = refs or RobinhoodCryptoCredentialRefs()
        self._environment = environment
        self._project_root = project_root

    def available(self) -> bool:
        environment = self._get_environment()
        api_key = environment.get(self._refs.api_key_env, "").strip()
        direct_key = environment.get(self._refs.private_key_env, "").strip()
        key_path = environment.get(self._refs.private_key_path_env, "").strip()
        return bool(api_key and (direct_key or key_path) and not (direct_key and key_path))

    def resolve(self) -> RobinhoodCryptoCredentials:
        environment = self._get_environment()
        api_key = environment.get(self._refs.api_key_env, "").strip()
        direct_key = environment.get(self._refs.private_key_env, "").strip()
        key_path_value = environment.get(self._refs.private_key_path_env, "").strip()

        if not api_key:
            raise RuntimeError(f"missing environment variable: {self._refs.api_key_env}")
        if direct_key and key_path_value:
            raise RuntimeError(
                "configure exactly one Robinhood Crypto private-key source: "
                f"{self._refs.private_key_env} or {self._refs.private_key_path_env}"
            )
        if not direct_key and not key_path_value:
            raise RuntimeError(
                "missing Robinhood Crypto private key; configure "
                f"{self._refs.private_key_env} or {self._refs.private_key_path_env}"
            )

        private_key = direct_key or self._read_private_key(key_path_value)
        return RobinhoodCryptoCredentials(api_key=api_key, private_key_base64=private_key)

    def _read_private_key(self, configured_path: str) -> str:
        path = Path(configured_path).expanduser()
        if not path.is_absolute() and self._project_root is not None:
            path = self._project_root / path
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"unable to read Robinhood Crypto private-key file: {path}") from exc
        if not value:
            raise RuntimeError(f"Robinhood Crypto private-key file is empty: {path}")
        return value

    def _get_environment(self) -> Mapping[str, str]:
        return self._environment if self._environment is not None else os.environ
