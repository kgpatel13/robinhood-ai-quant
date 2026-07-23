from __future__ import annotations

from src.core.events import Event, EventBus, MarketDataLoaded


def test_publish_delivers_typed_event() -> None:
    bus = EventBus()
    received: list[MarketDataLoaded] = []
    bus.subscribe(MarketDataLoaded, received.append)
    event = MarketDataLoaded(run_id="run", symbols=("SPY",), rows=10)
    assert bus.publish(event) == 1
    assert received == [event]


def test_base_event_subscription_receives_subclasses() -> None:
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe(Event, received.append)
    bus.publish(MarketDataLoaded(run_id="run"))
    assert len(received) == 1


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    received: list[MarketDataLoaded] = []
    bus.subscribe(MarketDataLoaded, received.append)
    bus.unsubscribe(MarketDataLoaded, received.append)
    assert bus.publish(MarketDataLoaded(run_id="run")) == 0


def test_duplicate_subscription_is_ignored() -> None:
    bus = EventBus()
    received: list[MarketDataLoaded] = []
    bus.subscribe(MarketDataLoaded, received.append)
    bus.subscribe(MarketDataLoaded, received.append)
    assert bus.subscriber_count(MarketDataLoaded) == 1
