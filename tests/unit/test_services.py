from __future__ import annotations

import pytest

from src.core.services import ServiceContainer, ServiceError


def test_instance_registration_and_resolution() -> None:
    container = ServiceContainer()
    container.register_instance("answer", 42)
    assert container.resolve("answer", int) == 42


def test_factory_is_lazy_and_singleton() -> None:
    container = ServiceContainer()
    calls = 0

    def factory(_: ServiceContainer) -> list[str]:
        nonlocal calls
        calls += 1
        return []

    container.register_factory("items", factory)
    first = container.resolve("items", list)
    second = container.resolve("items", list)
    assert first is second
    assert calls == 1


def test_unknown_service_fails() -> None:
    with pytest.raises(ServiceError, match="Unknown service"):
        ServiceContainer().resolve("missing")


def test_wrong_expected_type_fails() -> None:
    container = ServiceContainer()
    container.register_instance("value", "text")
    with pytest.raises(ServiceError, match="expected int"):
        container.resolve("value", int)


def test_duplicate_service_fails() -> None:
    container = ServiceContainer()
    container.register_instance("value", 1)
    with pytest.raises(ServiceError, match="already registered"):
        container.register_instance("value", 2)
