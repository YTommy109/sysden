import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from app import ai_service, table_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _check_table_name(name: str) -> None:
    if not table_service.validate_table_name(name):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid table name: '{name}'",
        )


def _rebuilding_response(sse_url: str, target: str, label: str) -> HTMLResponse:
    return HTMLResponse(
        f'<div sse-connect="{sse_url}"'
        f' hx-trigger="sse:complete" hx-get="/"'
        f' hx-select="{target}" hx-target="{target}" hx-swap="outerHTML"'
        f' style="margin:0;">'
        f'<button type="button" disabled aria-label="{label}" title="{label}"'
        f' style="background:#555; padding:0.3rem 0.45rem; line-height:0;">'
        f'<img src="/static/icons/arrow-path.svg" alt=""'
        f' style="width:1.1rem; height:1.1rem;" class="spinning">'
        f"</button></div>"
    )


@router.post("/tables")
def create_table(
    request: Request,
    prompt: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
) -> Response:
    if name is None:
        tables = ai_service.create_table_design(prompt)
    else:
        _check_table_name(name)
        tsv = ai_service.generate_table_design(prompt)
        default_md = f"# {name}\n\n## 概要\n\n## テーブル設計\n\n![[{name}.tsv]]\n"
        tables = [(name, tsv, default_md)]
    for tbl_name, _, _ in tables:
        _check_table_name(tbl_name)
        if table_service.table_exists(tbl_name):
            raise HTTPException(status_code=409, detail=f"Table '{tbl_name}' already exists")
    written: list[str] = []
    try:
        for tbl_name, tbl_tsv, tbl_md in tables:
            table_service.write_tsv(tbl_name, tbl_tsv)
            written.append(tbl_name)
            if tbl_md:
                table_service.write_markdown(tbl_name, tbl_md)
    except Exception:
        for written_name in written:
            table_service.delete_table(written_name)
        raise
    table_service.rebuild_index()
    redirect_url = f"/tables/{tables[0][0]}" if len(tables) == 1 else "/"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    _check_table_name(name)
    try:
        current_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    tsv = ai_service.generate_table_design(prompt, current_tsv)
    table_service.write_tsv(name, tsv)
    redirect_url = f"/tables/{name}"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/rebuild-index-tables")
def rebuild_index_tables(request: Request) -> Response:
    """テーブル一覧 (index.tsv) と ER 図 (index.mmd) を再生成してトップページへリダイレクトする。"""
    if request.headers.get("HX-Request"):
        return _rebuilding_response("/api/sse/rebuild-index", "#index-body", "テーブル一覧の再作成")
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.post("/rebuild-er-diagram")
def rebuild_er_diagram(request: Request) -> Response:
    """ER 図 (index.mmd) を再生成してトップページへリダイレクトする。"""
    if request.headers.get("HX-Request"):
        return _rebuilding_response("/api/sse/rebuild-er", "#er-diagram", "ER 図の再作成")
    table_service.rebuild_er_diagram_file()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    _check_table_name(name)
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    table_service.rebuild_index()
    return {"status": "deleted", "name": name}


_MIN_SPIN_SECONDS = 0.5


async def _sse_rebuild(func: Callable[[], object]) -> StreamingResponse:
    async def generate():
        t0 = asyncio.get_event_loop().time()
        try:
            await asyncio.to_thread(func)
        except Exception:
            logger.exception("%s failed", getattr(func, "__name__", func))
        elapsed = asyncio.get_event_loop().time() - t0
        remaining = _MIN_SPIN_SECONDS - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        yield "event: complete\ndata: done\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/sse/rebuild-index")
async def sse_rebuild_index() -> StreamingResponse:
    return await _sse_rebuild(table_service.rebuild_index)


@router.get("/sse/rebuild-er")
async def sse_rebuild_er() -> StreamingResponse:
    return await _sse_rebuild(table_service.rebuild_er_diagram_file)
