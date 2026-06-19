from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from app import table_service

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))
_md = MarkdownIt().enable("table")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    tables = table_service.list_tables()
    return templates.TemplateResponse(request, "index.html", {"tables": tables})


@router.get("/tables/{name}", response_class=HTMLResponse)
def table_detail(name: str, request: Request) -> HTMLResponse:
    try:
        rows = table_service.read_tsv(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    md_table = table_service.tsv_to_markdown(rows)
    rendered = _md.render(md_table)
    return templates.TemplateResponse(
        request, "table_detail.html", {"name": name, "rendered": rendered}
    )
