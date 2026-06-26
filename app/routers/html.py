import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app import table_service
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """テーブル一覧ページを表示する。

    Args:
        request: FastAPI リクエスト。

    Returns:
        テーブル一覧の HTML レスポンス。
    """
    index_doc = table_service.get_index()
    tables = [{"name": t.name, "display_name": t.logical_name} for t in index_doc.tables]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tables": tables, "er_diagram": index_doc.er_diagram, "rules": index_doc.rules},
    )


@router.get("/tables/{name}", response_class=HTMLResponse)
def table_detail(name: str, request: Request) -> HTMLResponse:
    """テーブル詳細ページを表示する。

    論理設計・物理設計・DAO をタブ切り替えで閲覧できる。

    Args:
        name: テーブル名。
        request: FastAPI リクエスト。

    Returns:
        テーブル詳細の HTML レスポンス。
    """
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")
    try:
        doc = table_service.get_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return templates.TemplateResponse(
        request,
        "table_detail.html",
        {
            "name": name,
            "display_name": doc.meta.logical_name,
            "symbol": doc.meta.symbol,
            "logical": doc.logical,
            "physical": doc.physical,
            "dao": doc.dao,
        },
    )
