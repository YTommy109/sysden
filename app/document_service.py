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
