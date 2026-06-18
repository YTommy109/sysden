import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.event_bus import event_bus

router = APIRouter()


async def _event_generator() -> AsyncGenerator[dict, None]:
    q = event_bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield {"data": event}
            except asyncio.TimeoutError:
                yield {"data": "ping"}
    except asyncio.CancelledError:
        pass
    finally:
        event_bus.unsubscribe(q)


@router.get("/events")
async def sse_events() -> EventSourceResponse:
    return EventSourceResponse(_event_generator())
