import asyncio

import pytest

from app.event_bus import EventBus, event_bus


@pytest.mark.asyncio
async def test_subscriber_receives_published_event() -> None:
    bus = EventBus()
    q = bus.subscribe()

    await bus.publish("job_finished:abc-123")

    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event == "job_finished:abc-123"


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive_event() -> None:
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    await bus.publish("document_updated:xyz")

    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1 == e2 == "document_updated:xyz"


@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving() -> None:
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)

    await bus.publish("job_failed:999")

    assert q.empty()


def test_module_level_instance_exists() -> None:
    assert event_bus is not None
