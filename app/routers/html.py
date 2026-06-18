import re
import uuid

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
) -> HTMLResponse:
    projects = await document_service.get_projects(session)
    return templates.TemplateResponse(request, "projects.html", {"projects": projects})


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail_page(
    project_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
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
) -> HTMLResponse:
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
) -> HTMLResponse:
    try:
        await document_service.get_document(session, document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    rev = await document_service.get_current_revision(session, document_id)
    rendered = _render_markdown(rev.content) if rev else ""
    return templates.TemplateResponse(
        request, "partials/preview.html", {"rendered_html": rendered}
    )
