from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .models import CredentialReference


@dataclass(frozen=True, slots=True)
class ResolvedCredentials:
    api_key: str
    api_secret: str


class EnvironmentCredentialManager:
    """Resolves secrets without persisting or logging their values."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self._environment = environment if environment is not None else os.environ

    def resolve(self, reference: CredentialReference) -> ResolvedCredentials:
        api_key = self._environment.get(reference.key_name, "")
        api_secret = self._environment.get(reference.secret_name, "")
        if not api_key or not api_secret:
            raise RuntimeError(
                f"missing credential variables for {reference.provider} in {reference.environment}"
            )
        return ResolvedCredentials(api_key=api_key, api_secret=api_secret)
