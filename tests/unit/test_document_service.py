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
