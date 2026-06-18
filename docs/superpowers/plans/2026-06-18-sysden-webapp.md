# sysden Web アプリ実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/web-app-design.md` の設計に従い、markdown + mermaid の設計書を AI 依頼で生成・管理する FastAPI Web アプリを構築する。

**Architecture:** FastAPI (uvicorn) + SQLModel (asyncpg) + Anthropic Agent SDK。AI ジョブは `asyncio.create_task` で非同期実行し、完了を SSE でブラウザに通知。フロントエンドは htmx + _hyperscript + mermaid.js。

**Tech Stack:** Python 3.14, FastAPI, SQLModel (SQLAlchemy 2 async), asyncpg, Alembic, Anthropic SDK (beta.agents), sse-starlette, Jinja2, htmx, _hyperscript, mermaid.js, pytest + testcontainers

## Global Constraints

- Python >= 3.14; async/await 必須; 型アノテーション必須
- 行長 100 文字以内 (Ruff 強制)
- 認知的複雑度 ≤ 10 (Ruff C901)
- `ANTHROPIC_API_KEY` は設定しない。SDK はサブスクリプション認証で動作する
- DB セッションは `async with AsyncSession(engine) as session:` パターン; `session.exec()` 使用 (session.execute() 禁止)
- テンプレートレスポンスは `templates.TemplateResponse(request, "tmpl.html", {...})` (Starlette 1.x 以降 API)
- カバレッジ 80% 以上; unit テストは 60 秒以内
- コミットメッセージ: Conventional Commits + 日本語 (例: `feat: ドキュメント CRUD を実装する`)

## File Map

```
app/
├── __init__.py
├── main.py              FastAPI app, lifespan (agent 初期化 + engine setup)
├── database.py          create_async_engine, get_session dependency
├── models.py            SQLModel models: Project, Document, Revision, AiJob
├── event_bus.py         EventBus class (asyncio.Queue ベース) + モジュールレベルインスタンス
├── document_service.py  Document/Revision CRUD (all async, takes AsyncSession)
├── ai_service.py        initialize_agent(), run_ai_job() (Anthropic Agent SDK)
└── routers/
    ├── __init__.py
    ├── api.py           JSON API: projects, ai-jobs, rollback
    ├── html.py          Jinja2 HTML pages: /, /projects/{id}, /documents/{id}, /preview
    └── events.py        SSE: GET /events
templates/
├── base.html            共通レイアウト (htmx + _hyperscript + mermaid.js CDN)
├── projects.html        プロジェクト一覧 + 新規作成フォーム
├── project_detail.html  ドキュメント一覧 + AI 新規依頼フォーム
├── document_viewer.html 3ペイン: プレビュー + 依頼ペイン + 履歴サイドバー
└── partials/
    └── preview.html     レンダリング済み markdown 断片 (htmx 部分取得用)
tests/
├── conftest.py          共通 fixtures (pytest-asyncio, event_loop)
├── unit/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_event_bus.py
│   ├── test_document_service.py
│   └── test_ai_service.py
└── integration/
    ├── __init__.py
    ├── conftest.py      testcontainers PostgreSQL, TestClient
    ├── test_api_routes.py
    ├── test_html_routes.py
    └── test_sse_route.py
alembic/
├── env.py
└── versions/
    └── 001_initial_schema.py
alembic.ini
docker-compose.yml
.env.example
```

---

### Task 1: DB Models + Database Setup + Alembic Migration

**Files:**
- Create: `app/__init__.py`
- Create: `app/models.py`
- Create: `app/database.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/001_initial_schema.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_models.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces:
  - `app.models.Project`, `app.models.Document`, `app.models.Revision`, `app.models.AiJob` (SQLModel table classes)
  - `app.database.engine` (AsyncEngine)
  - `app.database.get_session` (AsyncGenerator[AsyncSession, None])
  - `app.database.init_db()` (async, creates tables via SQLModel.metadata)

- [ ] **Step 1: Create `app/__init__.py` and `tests/__init__.py`**

```bash
mkdir -p app/routers tests/unit tests/integration
touch app/__init__.py app/routers/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

- [ ] **Step 2: Write `app/models.py` のテスト**

```python
# tests/unit/test_models.py
import uuid
from app.models import Project, Document, Revision, AiJob


def test_project_defaults():
    p = Project(name="Test", description="desc")
    assert p.name == "Test"
    assert isinstance(p.id, uuid.UUID)


def test_ai_job_default_status():
    job = AiJob(project_id=uuid.uuid4(), prompt="test", model="claude-opus-4-8")
    assert job.status == "pending"
    assert job.document_id is None
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'app'` or `ImportError`

- [ ] **Step 4: Write `app/models.py`**

```python
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: str = ""
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id")
    title: str
    current_revision_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Revision(SQLModel, table=True):
    __tablename__ = "revisions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="documents.id")
    rev_no: int
    content: str
    ai_job_id: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AiJob(SQLModel, table=True):
    __tablename__ = "ai_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id")
    document_id: Optional[uuid.UUID] = Field(default=None, foreign_key="documents.id")
    prompt: str
    status: str = "pending"
    model: str
    error: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
```

- [ ] **Step 5: Write `app/database.py`**

```python
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://sysden:sysden@localhost:5432/sysden"
)

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_models.py -v
```
Expected: 2 passed

- [ ] **Step 7: Set up Alembic**

```bash
uv run alembic init alembic
```

- [ ] **Step 8: Write `alembic/env.py`**

Replace generated `alembic/env.py` with:

```python
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context
import asyncio

from app.models import SQLModel  # noqa: F401 — registers all tables

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://sysden:sysden@localhost:5432/sysden"
).replace("postgresql+asyncpg", "postgresql+psycopg2")


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Note: Alembic uses sync engine. Add `psycopg2-binary` to dev deps or use `asyncpg` with the sync adapter.
Actually, add `psycopg2-binary` to dev dependencies:
```bash
uv add --dev psycopg2-binary
```

- [ ] **Step 9: Update `alembic.ini` database URL placeholder**

In `alembic.ini`, set:
```ini
sqlalchemy.url = postgresql+psycopg2://sysden:sysden@localhost:5432/sysden
```

- [ ] **Step 10: Create initial migration**

```bash
uv run alembic revision --autogenerate -m "initial schema"
```

Verify the generated file in `alembic/versions/` has `op.create_table("projects", ...)` etc.

- [ ] **Step 11: Write `tests/conftest.py`**

```python
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 12: Commit**

```bash
git add app/__init__.py app/models.py app/database.py alembic/ alembic.ini tests/
git commit -m "feat: DB モデルとデータベース設定を追加する"
```

---

### Task 2: EventBus

**Files:**
- Create: `app/event_bus.py`
- Create: `tests/unit/test_event_bus.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `app.event_bus.EventBus` class with `subscribe() -> asyncio.Queue[str]`, `unsubscribe(q)`, `publish(event: str) -> None`
  - `app.event_bus.event_bus` — モジュールレベルのシングルトンインスタンス

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_event_bus.py
import asyncio
import pytest
from app.event_bus import EventBus


@pytest.mark.asyncio
async def test_subscriber_receives_published_event():
    bus = EventBus()
    q = bus.subscribe()

    await bus.publish("job_finished:abc-123")

    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event == "job_finished:abc-123"


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive_event():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    await bus.publish("document_updated:xyz")

    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1 == e2 == "document_updated:xyz"


@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)

    await bus.publish("job_failed:999")

    assert q.empty()


def test_module_level_instance_exists():
    from app.event_bus import event_bus
    assert event_bus is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_event_bus.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.event_bus'`

- [ ] **Step 3: Write `app/event_bus.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_event_bus.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/event_bus.py tests/unit/test_event_bus.py
git commit -m "feat: EventBus を実装する"
```

---

### Task 3: DocumentService (CRUD)

**Files:**
- Create: `app/document_service.py`
- Create: `tests/unit/test_document_service.py`

**Interfaces:**
- Consumes: `app.models.{Project, Document, Revision, AiJob}`, `app.database.engine`
- Produces (all async, receive `AsyncSession` as first arg):
  - `create_project(session, name: str, description: str) -> Project`
  - `get_projects(session) -> list[Project]`
  - `get_project(session, project_id: uuid.UUID) -> Project`
  - `create_document(session, project_id: uuid.UUID, title: str) -> Document`
  - `get_documents(session, project_id: uuid.UUID) -> list[Document]`
  - `get_document(session, document_id: uuid.UUID) -> Document`
  - `get_current_revision(session, document_id: uuid.UUID) -> Revision | None`
  - `get_revisions(session, document_id: uuid.UUID) -> list[Revision]`
  - `add_revision(session, document_id: uuid.UUID, content: str, ai_job_id: uuid.UUID | None) -> Revision`
  - `rollback_to_revision(session, document_id: uuid.UUID, revision_id: uuid.UUID) -> Document`
  - `create_ai_job(session, project_id: uuid.UUID, prompt: str, document_id: uuid.UUID | None) -> AiJob`
  - `update_ai_job_status(session, job_id: uuid.UUID, status: str, error: str | None) -> AiJob`
  - `get_ai_job(session, job_id: uuid.UUID) -> AiJob`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_document_service.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import select

from app.models import Project, Document, Revision, AiJob
from app import document_service


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_create_project(mock_session):
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    project = await document_service.create_project(mock_session, "Test", "A test project")

    assert project.name == "Test"
    assert project.description == "A test project"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_document(mock_session):
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    project_id = uuid.uuid4()
    doc = await document_service.create_document(mock_session, project_id, "My Doc")

    assert doc.title == "My Doc"
    assert doc.project_id == project_id
    assert doc.current_revision_id is None


@pytest.mark.asyncio
async def test_add_revision_updates_current(mock_session):
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = Document(id=doc_id, project_id=uuid.uuid4(), title="T")
    mock_session.get = AsyncMock(return_value=mock_doc)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Mock exec to return rev_no = 0 (first revision)
    mock_result = MagicMock()
    mock_result.one_or_none.return_value = None
    mock_session.exec = AsyncMock(return_value=mock_result)

    rev = await document_service.add_revision(mock_session, doc_id, "# Hello", job_id)

    assert rev.rev_no == 1
    assert rev.content == "# Hello"
    assert mock_doc.current_revision_id == rev.id


@pytest.mark.asyncio
async def test_rollback_updates_current_revision_id(mock_session):
    doc_id = uuid.uuid4()
    old_rev_id = uuid.uuid4()
    target_rev_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id, project_id=uuid.uuid4(), title="T", current_revision_id=old_rev_id
    )
    mock_rev = Revision(
        id=target_rev_id, document_id=doc_id, rev_no=1, content="# Old"
    )
    mock_session.get = AsyncMock(side_effect=[mock_doc, mock_rev])
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await document_service.rollback_to_revision(
        mock_session, doc_id, target_rev_id
    )

    assert result.current_revision_id == target_rev_id
    mock_session.commit.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_document_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.document_service'`

- [ ] **Step 3: Write `app/document_service.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import AiJob, Document, Project, Revision


async def create_project(session: AsyncSession, name: str, description: str) -> Project:
    project = Project(name=name, description=description)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_projects(session: AsyncSession) -> list[Project]:
    result = await session.exec(select(Project).order_by(Project.created_at.desc()))
    return list(result.all())


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")
    return project


async def create_document(
    session: AsyncSession, project_id: uuid.UUID, title: str
) -> Document:
    doc = Document(project_id=project_id, title=title)
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def get_documents(session: AsyncSession, project_id: uuid.UUID) -> list[Document]:
    result = await session.exec(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.updated_at.desc())
    )
    return list(result.all())


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = await session.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    return doc


async def get_current_revision(
    session: AsyncSession, document_id: uuid.UUID
) -> Optional[Revision]:
    doc = await session.get(Document, document_id)
    if not doc or not doc.current_revision_id:
        return None
    return await session.get(Revision, doc.current_revision_id)


async def get_revisions(session: AsyncSession, document_id: uuid.UUID) -> list[Revision]:
    result = await session.exec(
        select(Revision)
        .where(Revision.document_id == document_id)
        .order_by(Revision.rev_no.desc())
    )
    return list(result.all())


async def add_revision(
    session: AsyncSession,
    document_id: uuid.UUID,
    content: str,
    ai_job_id: Optional[uuid.UUID] = None,
) -> Revision:
    doc = await session.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    # Get next rev_no
    result = await session.exec(
        select(Revision)
        .where(Revision.document_id == document_id)
        .order_by(Revision.rev_no.desc())
    )
    latest = result.one_or_none()
    next_rev_no = (latest.rev_no + 1) if latest else 1

    rev = Revision(
        document_id=document_id,
        rev_no=next_rev_no,
        content=content,
        ai_job_id=ai_job_id,
    )
    session.add(rev)
    await session.commit()
    await session.refresh(rev)

    doc.current_revision_id = rev.id
    doc.updated_at = datetime.utcnow()
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    return rev


async def rollback_to_revision(
    session: AsyncSession, document_id: uuid.UUID, revision_id: uuid.UUID
) -> Document:
    doc = await session.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    rev = await session.get(Revision, revision_id)
    if not rev or rev.document_id != document_id:
        raise ValueError(f"Revision {revision_id} not found for document {document_id}")

    doc.current_revision_id = revision_id
    doc.updated_at = datetime.utcnow()
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def create_ai_job(
    session: AsyncSession,
    project_id: uuid.UUID,
    prompt: str,
    document_id: Optional[uuid.UUID] = None,
    model: str = "claude-opus-4-8",
) -> AiJob:
    job = AiJob(project_id=project_id, prompt=prompt, document_id=document_id, model=model)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def update_ai_job_status(
    session: AsyncSession,
    job_id: uuid.UUID,
    status: str,
    error: Optional[str] = None,
) -> AiJob:
    job = await session.get(AiJob, job_id)
    if not job:
        raise ValueError(f"AiJob {job_id} not found")
    job.status = status
    job.error = error
    if status == "running":
        job.started_at = datetime.utcnow()
    elif status in ("succeeded", "failed"):
        job.finished_at = datetime.utcnow()
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_ai_job(session: AsyncSession, job_id: uuid.UUID) -> AiJob:
    job = await session.get(AiJob, job_id)
    if not job:
        raise ValueError(f"AiJob {job_id} not found")
    return job
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_document_service.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/document_service.py tests/unit/test_document_service.py
git commit -m "feat: DocumentService の CRUD を実装する"
```

---

### Task 4: AIService (Anthropic Agent SDK)

**Files:**
- Create: `app/ai_service.py`
- Create: `tests/unit/test_ai_service.py`

**Interfaces:**
- Consumes: `app.models.{AiJob, Document, Revision}`, `app.database.engine`, `app.document_service.*`, `app.event_bus.event_bus`
- Produces:
  - `app.ai_service.initialize_agent() -> None` — アプリ起動時に1回呼ぶ。`_agent_id` をモジュール変数にセット
  - `app.ai_service.run_ai_job(job_id: uuid.UUID) -> None` — asyncio.create_task で実行

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_ai_service.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import AiJob, Document, Revision


@pytest.mark.asyncio
async def test_initialize_agent_sets_agent_id():
    mock_agent = MagicMock()
    mock_agent.id = "agent-test-123"

    with patch("app.ai_service.client") as mock_client:
        mock_client.beta.agents.create = MagicMock(return_value=mock_agent)

        import app.ai_service as ai_svc
        ai_svc._agent_id = None
        await ai_svc.initialize_agent()

        assert ai_svc._agent_id == "agent-test-123"


@pytest.mark.asyncio
async def test_run_ai_job_success():
    job_id = uuid.uuid4()
    project_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_job = AiJob(
        id=job_id,
        project_id=project_id,
        document_id=doc_id,
        prompt="設計書を更新してください",
        status="pending",
        model="claude-opus-4-8",
    )
    mock_doc = Document(id=doc_id, project_id=project_id, title="Test Doc")
    mock_rev = Revision(
        id=uuid.uuid4(), document_id=doc_id, rev_no=1, content="# Old"
    )

    mock_turn = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "# Updated Doc\n\nContent here."
    mock_turn.content = [mock_block]

    mock_session_obj = MagicMock()
    mock_agent_session = MagicMock()
    mock_agent_session.id = "session-xyz"

    with (
        patch("app.ai_service._agent_id", "agent-test-123"),
        patch("app.ai_service.AsyncSession") as MockSession,
        patch("app.ai_service.client") as mock_client,
        patch("app.ai_service.event_bus") as mock_bus,
        patch("app.ai_service.document_service") as mock_ds,
    ):
        mock_client.beta.agents.sessions.create = MagicMock(
            return_value=mock_agent_session
        )
        mock_client.beta.agents.sessions.turns.create = MagicMock(
            return_value=mock_turn
        )
        mock_bus.publish = AsyncMock()
        mock_ds.get_ai_job = AsyncMock(return_value=mock_job)
        mock_ds.update_ai_job_status = AsyncMock(return_value=mock_job)
        mock_ds.get_document = AsyncMock(return_value=mock_doc)
        mock_ds.get_current_revision = AsyncMock(return_value=mock_rev)
        mock_ds.add_revision = AsyncMock(
            return_value=Revision(
                id=uuid.uuid4(), document_id=doc_id, rev_no=2, content="# Updated Doc\n\nContent here."
            )
        )

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session_obj)
        ctx.__aexit__ = AsyncMock(return_value=None)
        MockSession.return_value = ctx

        import app.ai_service as ai_svc
        await ai_svc.run_ai_job(job_id)

        mock_ds.update_ai_job_status.assert_any_await(
            mock_session_obj, job_id, "running"
        )
        mock_ds.add_revision.assert_awaited_once()
        mock_bus.publish.assert_awaited()


@pytest.mark.asyncio
async def test_run_ai_job_failure_records_error():
    job_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_job = AiJob(
        id=job_id,
        project_id=project_id,
        document_id=None,
        prompt="新規ドキュメントを作成",
        status="pending",
        model="claude-opus-4-8",
    )

    with (
        patch("app.ai_service._agent_id", "agent-test-123"),
        patch("app.ai_service.AsyncSession") as MockSession,
        patch("app.ai_service.client") as mock_client,
        patch("app.ai_service.event_bus") as mock_bus,
        patch("app.ai_service.document_service") as mock_ds,
    ):
        mock_client.beta.agents.sessions.create = MagicMock(
            side_effect=Exception("API error")
        )
        mock_bus.publish = AsyncMock()
        mock_ds.get_ai_job = AsyncMock(return_value=mock_job)
        mock_ds.update_ai_job_status = AsyncMock(return_value=mock_job)

        ctx = AsyncMock()
        session_mock = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=session_mock)
        ctx.__aexit__ = AsyncMock(return_value=None)
        MockSession.return_value = ctx

        import app.ai_service as ai_svc
        await ai_svc.run_ai_job(job_id)

        mock_ds.update_ai_job_status.assert_any_await(
            session_mock, job_id, "failed", error="API error"
        )
        mock_bus.publish.assert_any_await(f"job_failed:{job_id}")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_ai_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.ai_service'`

- [ ] **Step 3: Write `app/ai_service.py`**

```python
import re
import uuid
from typing import Optional

import anthropic
from sqlmodel.ext.asyncio.session import AsyncSession

from app import document_service
from app.database import engine
from app.event_bus import event_bus

client = anthropic.Anthropic()
_agent_id: Optional[str] = None

SYSTEM_PROMPT = """あなたはシステム設計ドキュメントのアシスタントです。
ユーザーの依頼に応じて、markdown + mermaid 形式のシステム設計書を生成または更新します。

出力規則:
- 出力はドキュメント本文のみ。前置き・説明・コードブロック外のコメントは不要
- 先頭は `# タイトル` の見出しで始める
- 図（アーキテクチャ・シーケンス・ER・フロー等）は mermaid フェンスブロックで記述する
- 既存ドキュメントの更新依頼では、変更箇所だけでなくドキュメント全体を返す
"""


async def initialize_agent() -> None:
    global _agent_id
    agent = client.beta.agents.create(
        model="claude-opus-4-8",
        name="sysden-assistant",
        system=SYSTEM_PROMPT,
    )
    _agent_id = agent.id


def _extract_title(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)", markdown, re.MULTILINE)
    return match.group(1).strip() if match else "無題のドキュメント"


async def run_ai_job(job_id: uuid.UUID) -> None:
    async with AsyncSession(engine) as session:
        job = await document_service.get_ai_job(session, job_id)
        await document_service.update_ai_job_status(session, job_id, "running")

        try:
            prompt = _build_prompt(job.prompt, None)
            if job.document_id:
                rev = await document_service.get_current_revision(session, job.document_id)
                if rev:
                    prompt = _build_prompt(job.prompt, rev.content)

            agent_session = client.beta.agents.sessions.create(agent_id=_agent_id)
            turn = client.beta.agents.sessions.turns.create(
                agent_id=_agent_id,
                session_id=agent_session.id,
                messages=[{"role": "user", "content": prompt}],
            )

            markdown = "\n".join(
                block.text for block in turn.content if hasattr(block, "text")
            )

            if job.document_id:
                await document_service.add_revision(
                    session, job.document_id, markdown, job.id
                )
                await document_service.update_ai_job_status(session, job_id, "succeeded")
                await event_bus.publish(f"job_finished:{job_id}")
                await event_bus.publish(f"document_updated:{job.document_id}")
            else:
                title = _extract_title(markdown)
                doc = await document_service.create_document(
                    session, job.project_id, title
                )
                await document_service.add_revision(session, doc.id, markdown, job.id)
                await document_service.update_ai_job_status(session, job_id, "succeeded")
                await event_bus.publish(f"job_finished:{job_id}")
                await event_bus.publish(f"document_updated:{doc.id}")

        except Exception as exc:
            await document_service.update_ai_job_status(
                session, job_id, "failed", error=str(exc)
            )
            await event_bus.publish(f"job_failed:{job_id}")


def _build_prompt(user_request: str, current_content: Optional[str]) -> str:
    if current_content:
        return f"現在のドキュメント:\n\n{current_content}\n\n---\n\n依頼: {user_request}"
    return user_request
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_ai_service.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/ai_service.py tests/unit/test_ai_service.py
git commit -m "feat: AIService (Anthropic Agent SDK) を実装する"
```

---

### Task 5: FastAPI Main App + API Router

**Files:**
- Create: `app/main.py`
- Create: `app/routers/api.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_api_routes.py`

**Interfaces:**
- Consumes: `app.database.{engine, get_session, init_db}`, `app.ai_service.initialize_agent`, `app.document_service.*`
- Produces:
  - `app.main.app` (FastAPI instance) — `from app.main import app`
  - Endpoints: `POST /api/projects`, `POST /api/projects/{id}/ai-jobs`, `POST /api/documents/{id}/ai-jobs`, `GET /api/ai-jobs/{id}`, `POST /api/documents/{id}/rollback`

- [ ] **Step 1: Write integration test conftest**

```python
# tests/integration/conftest.py
import pytest
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio

from app import models  # noqa: F401 — register table metadata


@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(postgres):
    url = postgres.get_connection_url()
    # testcontainers returns postgresql+psycopg2://..., convert to asyncpg
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session", autouse=True)
def setup_db(db_url):
    import app.database as db_module
    db_module.engine = create_async_engine(db_url, echo=False)

    async def _create():
        async with db_module.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_create())


@pytest.fixture(scope="session")
def client(setup_db):
    from app.main import app
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 2: Write failing API route tests**

```python
# tests/integration/test_api_routes.py
import pytest
from unittest.mock import patch, AsyncMock


def test_create_project(client):
    resp = client.post("/api/projects", json={"name": "My Project", "description": "desc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Project"
    assert "id" in data


def test_create_project_missing_name(client):
    resp = client.post("/api/projects", json={"description": "no name"})
    assert resp.status_code == 422


def test_create_ai_job_for_new_document(client):
    # First create a project
    proj = client.post(
        "/api/projects", json={"name": "Proj", "description": ""}
    ).json()
    proj_id = proj["id"]

    with patch("app.routers.api.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: None
        resp = client.post(
            f"/api/projects/{proj_id}/ai-jobs",
            json={"prompt": "新しい設計書を作ってください"},
        )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data


def test_get_ai_job_status(client):
    proj = client.post(
        "/api/projects", json={"name": "P2", "description": ""}
    ).json()
    proj_id = proj["id"]

    with patch("app.routers.api.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: None
        job_resp = client.post(
            f"/api/projects/{proj_id}/ai-jobs",
            json={"prompt": "test"},
        ).json()
    job_id = job_resp["job_id"]

    resp = client.get(f"/api/ai-jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_rollback_document(client):
    import uuid
    resp = client.post(
        f"/api/documents/{uuid.uuid4()}/rollback",
        json={"revision_id": str(uuid.uuid4())},
    )
    # non-existent document → 404
    assert resp.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_api_routes.py -v
```
Expected: ImportError or 404s

- [ ] **Step 4: Write `app/routers/api.py`**

```python
import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app import document_service
from app.ai_service import run_ai_job
from app.database import get_session

router = APIRouter(prefix="/api")


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class AiJobCreate(BaseModel):
    prompt: str


class RollbackRequest(BaseModel):
    revision_id: uuid.UUID


@router.post("/projects")
async def create_project(
    body: ProjectCreate, session: AsyncSession = Depends(get_session)
):
    project = await document_service.create_project(session, body.name, body.description)
    return project


@router.post("/projects/{project_id}/ai-jobs", status_code=202)
async def create_ai_job_for_project(
    project_id: uuid.UUID,
    body: AiJobCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        await document_service.get_project(session, project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    job = await document_service.create_ai_job(
        session, project_id, body.prompt, document_id=None
    )
    asyncio.create_task(run_ai_job(job.id))
    return {"job_id": str(job.id)}


@router.post("/documents/{document_id}/ai-jobs", status_code=202)
async def create_ai_job_for_document(
    document_id: uuid.UUID,
    body: AiJobCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        doc = await document_service.get_document(session, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    job = await document_service.create_ai_job(
        session, doc.project_id, body.prompt, document_id=document_id
    )
    asyncio.create_task(run_ai_job(job.id))
    return {"job_id": str(job.id)}


@router.get("/ai-jobs/{job_id}")
async def get_ai_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    try:
        job = await document_service.get_ai_job(session, job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/documents/{document_id}/rollback")
async def rollback_document(
    document_id: uuid.UUID,
    body: RollbackRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        doc = await document_service.rollback_to_revision(
            session, document_id, body.revision_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return doc
```

- [ ] **Step 5: Write `app/main.py`**

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.ai_service import initialize_agent
from app.database import init_db
from app.routers import api


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    await initialize_agent()
    yield


app = FastAPI(title="sysden", lifespan=lifespan)
app.include_router(api.router)

templates = Jinja2Templates(directory="templates")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_api_routes.py -v
```
Expected: 4-5 passed (some may fail due to DB connectivity in CI — acceptable if local passes)

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/routers/api.py tests/integration/
git commit -m "feat: FastAPI メインアプリと API ルーターを実装する"
```

---

### Task 6: SSE Router

**Files:**
- Create: `app/routers/events.py`
- Create: `tests/integration/test_sse_route.py`

**Interfaces:**
- Consumes: `app.event_bus.event_bus`, `app.main.app`
- Produces: `GET /events` — SSE ストリーム (EventSourceResponse)

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_sse_route.py
from fastapi.routing import APIRoute


def test_events_route_is_registered():
    from app.main import app
    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert "/events" in paths
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/test_sse_route.py -v
```
Expected: AssertionError (route not registered)

- [ ] **Step 3: Write `app/routers/events.py`**

```python
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
```

- [ ] **Step 4: Register SSE router in `app/main.py`**

Edit `app/main.py` — add router import and include:

```python
from app.routers import api, events   # add events

# in app setup (after app = FastAPI(...)):
app.include_router(api.router)
app.include_router(events.router)    # add this line
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/integration/test_sse_route.py -v
```
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add app/routers/events.py tests/integration/test_sse_route.py app/main.py
git commit -m "feat: SSE エンドポイントを追加する"
```

---

### Task 7: HTML Router + Jinja2 Templates

**Files:**
- Create: `app/routers/html.py`
- Create: `templates/base.html`
- Create: `templates/projects.html`
- Create: `templates/project_detail.html`
- Create: `templates/document_viewer.html`
- Create: `templates/partials/preview.html`
- Create: `tests/integration/test_html_routes.py`

**Interfaces:**
- Consumes: `app.document_service.*`, `app.main.templates`, FastAPI `Request`
- Produces: HTML pages at `GET /`, `GET /projects/{id}`, `GET /documents/{id}`, `GET /documents/{id}/preview`
- markdown → HTML: `markdown_it.MarkdownIt().render(content)` — mermaid フェンスは `<pre class="mermaid">` に変換

- [ ] **Step 1: Write failing HTML route tests**

```python
# tests/integration/test_html_routes.py
import pytest


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_project_page_404_for_unknown(client):
    import uuid
    resp = client.get(f"/projects/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_document_page_404_for_unknown(client):
    import uuid
    resp = client.get(f"/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_root_page_contains_project_list_element(client):
    resp = client.get("/")
    assert b"sysden" in resp.content or b"project" in resp.content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_html_routes.py -v
```
Expected: 404 or ImportError

- [ ] **Step 3: Write `app/routers/html.py`**

```python
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from sqlmodel.ext.asyncio.session import AsyncSession

from app import document_service
from app.database import get_session

router = APIRouter()
templates = Jinja2Templates(directory="templates")
_md = MarkdownIt()


def _render_markdown(content: str) -> str:
    """markdown → HTML。mermaid フェンスは <pre class="mermaid"> に変換する。"""
    import re
    content = re.sub(
        r"```mermaid\n(.*?)```",
        r'<pre class="mermaid">\1</pre>',
        content,
        flags=re.DOTALL,
    )
    return _md.render(content)


@router.get("/", response_class=HTMLResponse)
async def projects_page(
    request: Request, session: AsyncSession = Depends(get_session)
):
    projects = await document_service.get_projects(session)
    return templates.TemplateResponse(request, "projects.html", {"projects": projects})


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail_page(
    project_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        project = await document_service.get_project(session, project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    documents = await document_service.get_documents(session, project_id)
    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {"project": project, "documents": documents},
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
async def document_viewer_page(
    document_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        doc = await document_service.get_document(session, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    rev = await document_service.get_current_revision(session, document_id)
    revisions = await document_service.get_revisions(session, document_id)
    rendered = _render_markdown(rev.content) if rev else ""
    return templates.TemplateResponse(
        request,
        "document_viewer.html",
        {
            "doc": doc,
            "rendered_html": rendered,
            "revisions": revisions,
            "current_rev": rev,
        },
    )


@router.get("/documents/{document_id}/preview", response_class=HTMLResponse)
async def document_preview(
    document_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    try:
        await document_service.get_document(session, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    rev = await document_service.get_current_revision(session, document_id)
    rendered = _render_markdown(rev.content) if rev else ""
    return templates.TemplateResponse(
        request, "partials/preview.html", {"rendered_html": rendered}
    )
```

- [ ] **Step 4: Register HTML router in `app/main.py`**

```python
from app.routers import api, events, html   # add html

app.include_router(api.router)
app.include_router(events.router)
app.include_router(html.router)             # add this line
```

- [ ] **Step 5: Create `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}sysden{% endblock %}</title>
  <style>
    body { font-family: sans-serif; margin: 0; padding: 0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
    nav { background: #1a1a2e; color: white; padding: 0.75rem 1rem; }
    nav a { color: white; text-decoration: none; margin-right: 1rem; }
    .mermaid { overflow-x: auto; }
    #error-panel { display: none; border: 2px solid red; padding: 1rem; font-family: monospace; white-space: pre-wrap; }
  </style>
</head>
<body>
  <nav>
    <a href="/">sysden</a>
    {% block nav_extra %}{% endblock %}
  </nav>
  <div class="container">
    {% block content %}{% endblock %}
  </div>

  <script src="https://unpkg.com/htmx.org@2.0.4" defer></script>
  <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js" defer></script>
  <script src="https://unpkg.com/hyperscript.org@0.9.14" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      sequence: { useMaxWidth: false }, er: { useMaxWidth: false },
      flowchart: { useMaxWidth: false }, gantt: { useMaxWidth: false },
      journey: { useMaxWidth: false }, pie: { useMaxWidth: false },
      state: { useMaxWidth: false }, class: { useMaxWidth: false },
    });
    document.addEventListener('DOMContentLoaded', () => mermaid.run({ querySelector: '.mermaid' }));
    mermaid.parseError = (err) => {
      const panel = document.getElementById('error-panel');
      if (panel) { panel.style.display = 'block'; panel.textContent = err; }
    };
  </script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 6: Create `templates/projects.html`**

```html
{% extends "base.html" %}
{% block title %}プロジェクト一覧 — sysden{% endblock %}
{% block content %}
<h1>プロジェクト一覧</h1>

<form hx-post="/api/projects" hx-target="#project-list" hx-swap="afterbegin" style="margin-bottom:1.5rem;">
  <input name="name" placeholder="プロジェクト名" required style="padding:0.5rem; width:300px;">
  <input name="description" placeholder="説明（任意）" style="padding:0.5rem; width:300px;">
  <button type="submit">作成</button>
</form>

<div id="project-list">
  {% for p in projects %}
  <div style="border:1px solid #ccc; padding:1rem; margin-bottom:0.75rem; border-radius:4px;">
    <a href="/projects/{{ p.id }}"><strong>{{ p.name }}</strong></a>
    {% if p.description %}<p style="color:#666; margin:0.25rem 0;">{{ p.description }}</p>{% endif %}
    <small style="color:#999;">{{ p.created_at.strftime('%Y-%m-%d %H:%M') }}</small>
  </div>
  {% else %}
  <p>プロジェクトはまだありません。</p>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 7: Create `templates/project_detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ project.name }} — sysden{% endblock %}
{% block nav_extra %}<a href="/projects/{{ project.id }}">{{ project.name }}</a>{% endblock %}
{% block content %}
<h1>{{ project.name }}</h1>
{% if project.description %}<p>{{ project.description }}</p>{% endif %}

<h2>AI に新規ドキュメントを依頼</h2>
<form hx-post="/api/projects/{{ project.id }}/ai-jobs"
      hx-target="#job-status" hx-swap="innerHTML"
      style="margin-bottom:1.5rem;">
  <textarea name="prompt" rows="3" placeholder="作成したい設計書の内容を説明してください"
    style="width:100%; padding:0.5rem; box-sizing:border-box;"></textarea>
  <button type="submit" style="margin-top:0.5rem;">依頼を送信</button>
</form>
<div id="job-status"></div>

<h2>ドキュメント一覧</h2>
<ul>
  {% for doc in documents %}
  <li><a href="/documents/{{ doc.id }}">{{ doc.title }}</a>
    <small style="color:#999;"> — {{ doc.updated_at.strftime('%Y-%m-%d %H:%M') }}</small>
  </li>
  {% else %}
  <li>ドキュメントはまだありません。</li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 8: Create `templates/partials/preview.html`**

```html
<div id="preview-content">
  {{ rendered_html | safe }}
</div>
<div id="error-panel" style="display:none; border:2px solid red; padding:1rem; font-family:monospace; white-space:pre-wrap;"></div>
<script>mermaid.run({ querySelector: '#preview-content .mermaid' });</script>
```

- [ ] **Step 9: Create `templates/document_viewer.html`**

```html
{% extends "base.html" %}
{% block title %}{{ doc.title }} — sysden{% endblock %}
{% block nav_extra %}
<a href="/projects/{{ doc.project_id }}">← プロジェクト</a>
{% endblock %}
{% block content %}
<div style="display:flex; gap:1rem; align-items:flex-start;">

  <!-- メインプレビュー -->
  <main style="flex:1; min-width:0;" id="main-preview"
    _="on load set my style.transform to 'scale(' + (localStorage.getItem('zoom') or '1') + ')' and set my style.transformOrigin to 'top left'"
    _="on keydown[key=='=' and (ctrlKey or metaKey)] halt
         set zoom to Math.min((parseFloat(localStorage.getItem('zoom') or '1') + 0.1).toFixed(1), 2.0)
         set localStorage['zoom'] to zoom
         set my style.transform to 'scale(' + zoom + ')'"
    _="on keydown[key=='-' and (ctrlKey or metaKey)] halt
         set zoom to Math.max((parseFloat(localStorage.getItem('zoom') or '1') - 0.1).toFixed(1), 0.5)
         set localStorage['zoom'] to zoom
         set my style.transform to 'scale(' + zoom + ')'">

    <div hx-ext="sse" sse-connect="/events">
      <div sse-swap="document_updated:{{ doc.id }}"
           hx-get="/documents/{{ doc.id }}/preview"
           hx-target="#preview-area"
           hx-swap="innerHTML"></div>
    </div>

    <div id="preview-area">
      {% include "partials/preview.html" %}
    </div>
  </main>

  <!-- 履歴サイドバー -->
  <aside id="history-sidebar" style="width:260px; border-left:1px solid #ccc; padding-left:1rem;">
    <h3>リビジョン履歴</h3>
    <ul style="list-style:none; padding:0; margin:0;">
      {% for rev in revisions %}
      <li style="margin-bottom:0.5rem; {% if current_rev and rev.id == current_rev.id %}font-weight:bold;{% endif %}">
        <span>Rev {{ rev.rev_no }} — {{ rev.created_at.strftime('%m/%d %H:%M') }}</span>
        {% if not (current_rev and rev.id == current_rev.id) %}
        <form hx-post="/api/documents/{{ doc.id }}/rollback"
              hx-target="#preview-area" hx-swap="innerHTML"
              style="display:inline;">
          <input type="hidden" name="revision_id" value="{{ rev.id }}">
          <button type="submit" style="font-size:0.75rem;">このバージョンに戻す</button>
        </form>
        {% endif %}
      </li>
      {% endfor %}
    </ul>
  </aside>
</div>

<!-- 依頼ペイン（下部固定） -->
<div style="position:fixed; bottom:0; left:0; right:0; background:white; border-top:1px solid #ccc; padding:0.75rem 1rem; display:flex; gap:0.5rem; align-items:flex-end;">
  <textarea id="prompt-input" rows="2" placeholder="依頼文を入力してください"
    style="flex:1; padding:0.5rem; resize:vertical; box-sizing:border-box;"></textarea>

  <div hx-ext="sse" sse-connect="/events">
    <div sse-swap="job_finished:*"
         hx-get="/documents/{{ doc.id }}/preview"
         hx-target="#preview-area"
         hx-swap="innerHTML"></div>
  </div>

  <button id="submit-btn"
    hx-post="/api/documents/{{ doc.id }}/ai-jobs"
    hx-include="#prompt-input"
    hx-target="#job-status-inline"
    hx-swap="innerHTML">送信</button>
  <span id="job-status-inline" style="font-size:0.85rem; color:#666;"></span>
</div>
<div style="height:80px;"></div><!-- 固定フッター分のスペーサー -->
{% endblock %}
```

- [ ] **Step 10: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_html_routes.py -v
```
Expected: 4 passed

- [ ] **Step 11: Commit**

```bash
git add app/routers/html.py app/main.py templates/ tests/integration/test_html_routes.py
git commit -m "feat: HTML ルーターと Jinja2 テンプレートを実装する"
```

---

### Task 8: Docker Compose + .env + Final Check

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `app/database.py` (環境変数から DATABASE_URL を読む — 既存)

**Interfaces:**
- Consumes: all previous tasks
- Produces: `docker compose up` で app + postgres が起動し `http://localhost:8000` でアクセス可能

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: sysden
      POSTGRES_PASSWORD: sysden
      POSTGRES_DB: sysden
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sysden"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://sysden:sysden@postgres:5432/sysden
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - .:/app
    command: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
COPY . .
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Write `.env.example`**

```
# ローカル開発用環境変数サンプル
# .env にコピーして使う（.env は .gitignore 対象）
DATABASE_URL=postgresql+asyncpg://sysden:sysden@localhost:5432/sysden

# ANTHROPIC_API_KEY は設定しないこと。
# SDK はサブスクリプション認証で動作する。
# 設定すると Max プランの枠外で API 課金が発生する。
```

- [ ] **Step 4: Update `.gitignore` to include `.env`**

Append to `.gitignore`:
```
.env
```

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/unit tests/integration -v --cov --cov-report=term-missing
```

Expected: all unit tests pass; coverage ≥ 80%

- [ ] **Step 6: Run lint and typecheck**

```bash
uv run ruff check . && uv run ruff format --check .
```

Fix any lint errors, then:

```bash
uv run ty check
```

Fix any type errors.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml Dockerfile .env.example .gitignore
git commit -m "chore: Docker Compose とアプリ起動設定を追加する"
```

---

## Self-Review: Spec Coverage

| 設計書セクション | 対応タスク |
|---|---|
| DB スキーマ (projects/documents/revisions/ai_jobs) | Task 1 |
| EventBus (asyncio.Queue) | Task 2 |
| document_service CRUD | Task 3 |
| AI 依頼フロー (Agent SDK, asyncio.create_task) | Task 4 + Task 5 |
| SSE (/events, 3イベント種別) | Task 6 |
| API ルート (5エンドポイント) | Task 5 |
| HTML ルート (4エンドポイント) | Task 7 |
| markdown → HTML + mermaid レンダリング | Task 7 (html.py `_render_markdown`) |
| 3ペイン UI (プレビュー + 依頼ペイン + 履歴) | Task 7 (document_viewer.html) |
| ズーム機能 (_hyperscript) | Task 7 (document_viewer.html) |
| ロールバック (current_revision_id 付け替え) | Task 3 + Task 5 |
| Docker Compose (app + postgres) | Task 8 |
| エラー処理 (failed status, error panel) | Task 4 (ai_service) + Task 7 (templates) |
| Alembic マイグレーション | Task 1 |
| テスト (unit + integration + sse route check) | 各タスク |
