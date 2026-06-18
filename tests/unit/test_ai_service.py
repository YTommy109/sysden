import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AiJob, Revision


@pytest.mark.asyncio
async def test_ensure_agent_sets_agent_id():
    mock_agent = MagicMock()
    mock_agent.id = "agent-test-123"
    mock_client = MagicMock()
    mock_client.beta.agents.create = MagicMock(return_value=mock_agent)

    with patch("app.ai_service._get_client", return_value=mock_client):
        import app.ai_service as ai_svc

        ai_svc._agent_id = None
        result = await ai_svc._ensure_agent()

        assert result == "agent-test-123"
        assert ai_svc._agent_id == "agent-test-123"


@pytest.mark.asyncio
async def test_run_ai_job_success() -> None:
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
    mock_rev = Revision(id=uuid.uuid4(), document_id=doc_id, rev_no=1, content="# Old")

    mock_turn = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "# Updated Doc\n\nContent here."
    mock_turn.content = [mock_block]

    mock_agent_session = MagicMock()
    mock_agent_session.id = "session-xyz"

    mock_client = MagicMock()
    mock_client.beta.agents.sessions.create = MagicMock(return_value=mock_agent_session)
    mock_client.beta.agents.sessions.turns.create = MagicMock(return_value=mock_turn)

    mock_session_obj = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session_obj)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.ai_service._agent_id", "agent-test-123"),
        patch("app.ai_service._ensure_agent", new=AsyncMock(return_value="agent-test-123")),
        patch("app.ai_service._get_client", return_value=mock_client),
        patch("app.ai_service.AsyncSession", return_value=ctx),
        patch("app.ai_service.event_bus") as mock_bus,
        patch("app.ai_service.document_service") as mock_ds,
    ):
        mock_bus.publish = AsyncMock()
        mock_ds.get_ai_job = AsyncMock(return_value=mock_job)
        mock_ds.update_ai_job_status = AsyncMock(return_value=mock_job)
        mock_ds.get_current_revision = AsyncMock(return_value=mock_rev)
        mock_ds.add_revision = AsyncMock(
            return_value=Revision(
                id=uuid.uuid4(),
                document_id=doc_id,
                rev_no=2,
                content="# Updated Doc\n\nContent here.",
            )
        )

        import app.ai_service as ai_svc

        await ai_svc.run_ai_job(job_id)

        mock_ds.update_ai_job_status.assert_any_await(mock_session_obj, job_id, "running")
        mock_ds.add_revision.assert_awaited_once()
        mock_bus.publish.assert_awaited()


@pytest.mark.asyncio
async def test_run_ai_job_failure_records_error() -> None:
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

    mock_client = MagicMock()
    mock_client.beta.agents.sessions.create = MagicMock(side_effect=Exception("API error"))

    session_mock = MagicMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.ai_service._ensure_agent", new=AsyncMock(return_value="agent-test-123")),
        patch("app.ai_service._get_client", return_value=mock_client),
        patch("app.ai_service.AsyncSession", return_value=ctx),
        patch("app.ai_service.event_bus") as mock_bus,
        patch("app.ai_service.document_service") as mock_ds,
    ):
        mock_bus.publish = AsyncMock()
        mock_ds.get_ai_job = AsyncMock(return_value=mock_job)
        mock_ds.update_ai_job_status = AsyncMock(return_value=mock_job)

        import app.ai_service as ai_svc

        await ai_svc.run_ai_job(job_id)

        mock_ds.update_ai_job_status.assert_any_await(
            session_mock, job_id, "failed", error="API error"
        )
        mock_bus.publish.assert_any_await(f"job_failed:{job_id}")
