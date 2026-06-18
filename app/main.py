from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.ai_service import initialize_agent
from app.database import init_db
from app.routers import api, events, html


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await initialize_agent()
    yield


app = FastAPI(title="sysden", lifespan=lifespan)
app.include_router(api.router)
app.include_router(events.router)
app.include_router(html.router)
