import uuid

from app.models import AiJob, Project


def test_project_defaults() -> None:
    p = Project(name="Test", description="desc")
    assert p.name == "Test"
    assert isinstance(p.id, uuid.UUID)


def test_ai_job_default_status() -> None:
    job = AiJob(project_id=uuid.uuid4(), prompt="test", model="claude-opus-4-8")
    assert job.status == "pending"
    assert job.document_id is None
