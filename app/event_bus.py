import asyncio


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.remove(q)

    async def publish(self, event: str) -> None:
        for q in self._subscribers:
            await q.put(event)


event_bus = EventBus()
