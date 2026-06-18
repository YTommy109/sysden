import asyncio
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app import document_service
from app.ai_service import run_ai_job
from app.database import get_session

router = APIRouter(prefix="/api")


@router.post("/projects")
async def create_project(
    name: str = Form(...),
    description: str = Form(""),
    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await document_service.create_project(session, name, description)
    return project.model_dump()


@router.post("/projects/{project_id}/ai-jobs", status_code=202)
async def create_ai_job_for_project(
    project_id: uuid.UUID,
    prompt: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await document_service.get_project(session, project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    job = await document_service.create_ai_job(session, project_id, prompt, document_id=None)
    asyncio.create_task(run_ai_job(job.id))
    return {"job_id": str(job.id)}


@router.post("/documents/{document_id}/ai-jobs", status_code=202)
async def create_ai_job_for_document(
    document_id: uuid.UUID,
    prompt: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        doc = await document_service.get_document(session, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")

    job = await document_service.create_ai_job(
        session, doc.project_id, prompt, document_id=document_id
    )
    asyncio.create_task(run_ai_job(job.id))
    return {"job_id": str(job.id)}


@router.get("/ai-jobs/{job_id}")
async def get_ai_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        job = await document_service.get_ai_job(session, job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@router.post("/documents/{document_id}/rollback")
async def rollback_document(
    document_id: uuid.UUID,
    revision_id: uuid.UUID = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        doc = await document_service.rollback_to_revision(session, document_id, revision_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return doc.model_dump()
