from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from src.common.exceptions import QuantPlatformError

T = TypeVar("T")
Factory = Callable[["ServiceContainer"], Any]


class ServiceError(QuantPlatformError):
    """Raised when service registration or resolution fails."""


class ServiceContainer:
    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Factory] = {}

    def register_instance(self, name: str, instance: Any, *, replace: bool = False) -> None:
        if self.contains(name) and not replace:
            raise ServiceError(f"Service already registered: {name}")
        self._factories.pop(name, None)
        self._instances[name] = instance

    def register_factory(self, name: str, factory: Factory, *, replace: bool = False) -> None:
        if self.contains(name) and not replace:
            raise ServiceError(f"Service already registered: {name}")
        self._instances.pop(name, None)
        self._factories[name] = factory

    def contains(self, name: str) -> bool:
        return name in self._instances or name in self._factories

    def resolve(self, name: str, expected_type: type[T] | None = None) -> T:
        if name not in self._instances:
            factory = self._factories.get(name)
            if factory is None:
                raise ServiceError(f"Unknown service: {name}")
            self._instances[name] = factory(self)
        value = self._instances[name]
        if expected_type is not None and not isinstance(value, expected_type):
            raise ServiceError(
                f"Service {name} is {type(value).__name__}, expected {expected_type.__name__}"
            )
        return cast(T, value)

    def names(self) -> list[str]:
        return sorted(set(self._instances) | set(self._factories))

    def clear(self) -> None:
        self._instances.clear()
        self._factories.clear()
