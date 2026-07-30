from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.robinhood_platform.models import RobinhoodCredentialRefs


@dataclass(frozen=True, slots=True)
class ResolvedRobinhoodCredentials:
    api_key: str
    private_key: str

    def __post_init__(self) -> None:
        if not self.api_key or not self.private_key:
            raise ValueError("resolved Robinhood credentials cannot be empty")


class RobinhoodCredentialManager:
    def __init__(
        self,
        refs: RobinhoodCredentialRefs | None = None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._refs = refs or RobinhoodCredentialRefs()
        self._environment = environment

    def available(self) -> bool:
        environment = self._get_environment()
        return bool(
            environment.get(self._refs.api_key_env) and environment.get(self._refs.private_key_env)
        )

    def resolve(self) -> ResolvedRobinhoodCredentials:
        environment = self._get_environment()
        api_key = environment.get(self._refs.api_key_env, "").strip()
        private_key = environment.get(self._refs.private_key_env, "").strip()
        if not api_key or not private_key:
            raise RuntimeError("required Robinhood credential variables are missing")
        return ResolvedRobinhoodCredentials(api_key=api_key, private_key=private_key)

    def _get_environment(self) -> Mapping[str, str]:
        if self._environment is not None:
            return self._environment
        import os

        return os.environ
