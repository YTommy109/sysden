import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from app import ai_service, symbol_service, table_service
from app.toon_io import read_index_toon

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _check_table_name(name: str) -> None:
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")


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
) -> Response:
    logger.info("テーブル作成リクエスト: prompt_length=%d", len(prompt))
    index = read_index_toon()
    designs = ai_service.create_table_design(
        prompt=prompt,
        rules=index.rules,
        existing_tables=index.tables,
    )

    for doc in designs:
        _check_table_name(doc.meta.physical_name)
        if table_service.table_exists(doc.meta.physical_name):
            raise HTTPException(
                status_code=409,
                detail=f"Table '{doc.meta.physical_name}' already exists",
            )

    table_symbols = [symbol_service.allocate_table_symbol() for _ in designs]
    placeholder_map: dict[str, str] = {}
    for i, _doc in enumerate(designs):
        placeholder = f"NEW_{i + 1}"
        placeholder_map[placeholder] = table_symbols[i]
    designs = symbol_service.remap_placeholders(
        designs, placeholder_map, table_symbols=table_symbols
    )

    written: list[str] = []
    try:
        for doc in designs:
            doc = table_service.derive_all(doc)
            name = doc.meta.physical_name
            table_service.save_table(name, doc)
            written.append(name)
    except Exception:
        for name in written:
            table_service.delete_table(name)
        raise
    table_service.rebuild_index()
    logger.info(
        "テーブル作成完了: tables=%s",
        [d.meta.physical_name for d in designs],
    )
    redirect_url = f"/tables/{designs[0].meta.physical_name}" if len(designs) == 1 else "/"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    logger.info("テーブル更新リクエスト: table=%s", name)
    _check_table_name(name)
    try:
        current = table_service.get_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    index = read_index_toon()
    updated = ai_service.update_table_design(
        prompt=prompt,
        current=current,
        rules=index.rules,
        existing_tables=index.tables,
    )
    updated = updated.model_copy(
        update={"meta": updated.meta.model_copy(update={"symbol": current.meta.symbol})}
    )
    updated = table_service.derive_all(updated)
    table_service.save_table(name, updated)
    table_service.rebuild_index()
    logger.info("テーブル更新完了: table=%s", name)
    redirect_url = f"/tables/{name}"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/rebuild-index-tables")
def rebuild_index_tables(request: Request) -> Response:
    if request.headers.get("HX-Request"):
        return _rebuilding_response("/api/sse/rebuild-index", "#index-body", "テーブル一覧の再作成")
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.post("/rebuild-er-diagram")
def rebuild_er_diagram(request: Request) -> Response:
    if request.headers.get("HX-Request"):
        return _rebuilding_response("/api/sse/rebuild-er", "#er-diagram", "ER 図の再作成")
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    _check_table_name(name)
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    table_service.rebuild_index()
    logger.info("テーブル削除完了: table=%s", name)
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
    return await _sse_rebuild(table_service.rebuild_index)
