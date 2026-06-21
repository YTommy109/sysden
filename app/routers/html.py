import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from app import table_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))
_md = MarkdownIt("commonmark", {"html": True}).enable("table")


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """テーブル一覧ページを表示する。"""
    tables = table_service.read_index_tables()
    er_diagram = table_service.read_er_diagram()
    return templates.TemplateResponse(
        request, "index.html", {"tables": tables, "er_diagram": er_diagram}
    )


@router.get("/tables/{name}", response_class=HTMLResponse)
def table_detail(name: str, request: Request) -> HTMLResponse:
    """テーブル詳細ページを表示する。

    markdown が存在する場合は埋め込み TSV を展開してレンダリングする。
    """
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")
    try:
        rows = table_service.read_tsv(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err

    display_name = table_service.read_table_display_name(name)

    md_content = table_service.read_markdown(name)
    if md_content is not None:
        body = table_service.strip_title_heading(md_content)
        expanded = table_service.render_markdown_with_embeds(body)
        rendered = _md.render(expanded)
    else:
        md_table = table_service.tsv_to_markdown(rows)
        rendered = _md.render(md_table)

    return templates.TemplateResponse(
        request,
        "table_detail.html",
        {"name": name, "display_name": display_name, "rendered": rendered},
    )
