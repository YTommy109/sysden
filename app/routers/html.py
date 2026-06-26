import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from app import table_service
from app.toon_io import read_index_toon

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))
_md = MarkdownIt("commonmark", {"html": True}).enable("table")


def _dict_list_to_markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_（データなし）_"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    index_doc = read_index_toon()
    tables = [{"name": t.name, "display_name": t.logical_name} for t in index_doc.tables]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tables": tables, "er_diagram": index_doc.er_diagram, "rules": index_doc.rules},
    )


@router.get("/tables/{name}", response_class=HTMLResponse)
def table_detail(name: str, request: Request) -> HTMLResponse:
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")
    try:
        doc = table_service.get_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    logical_html = ""
    physical_html = ""
    dao_html = ""

    if doc.logical:
        logical_html = _md.render(_dict_list_to_markdown_table(doc.logical))
        logical_html = logical_html.replace(
            "<td>* ",
            '<td><span style="color:red;font-weight:bold;">*</span> ',
        )
    if doc.physical:
        physical_html = _md.render(_dict_list_to_markdown_table(doc.physical))
    if doc.dao:
        dao_html = _md.render(_dict_list_to_markdown_table(doc.dao))

    return templates.TemplateResponse(
        request,
        "table_detail.html",
        {
            "name": name,
            "display_name": doc.meta.logical_name,
            "symbol": doc.meta.symbol,
            "logical_html": logical_html,
            "physical_html": physical_html,
            "dao_html": dao_html,
        },
    )
