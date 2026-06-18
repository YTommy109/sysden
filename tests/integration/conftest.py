import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from testcontainers.postgres import PostgresContainer

from app import models  # noqa: F401 — register table metadata


@pytest.fixture(scope="session")
def postgres():
    try:
        with PostgresContainer("postgres:16") as pg:
            yield pg
    except Exception:
        pytest.skip("Docker not available")


@pytest.fixture(scope="session")
def db_url(postgres: PostgresContainer) -> str:
    url = postgres.get_connection_url()
    # testcontainers returns postgresql+psycopg2://..., convert to asyncpg
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session", autouse=True)
def setup_db(request: pytest.FixtureRequest) -> None:
    try:
        db_url_val = request.getfixturevalue("db_url")
    except Exception:
        # Docker not available, skip DB setup
        return

    import app.database as db_module

    db_module.engine = create_async_engine(db_url_val, echo=False)

    async def _create() -> None:
        async with db_module.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.run(_create())


@pytest.fixture(scope="session")
def client(setup_db: None):
    with patch("app.ai_service.initialize_agent", new_callable=AsyncMock):
        from app.main import app

        with TestClient(app) as c:
            yield c
