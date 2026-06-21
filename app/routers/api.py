import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from app import ai_service, table_service
from app.config import get_data_dir

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
    """AI にテーブル設計を生成させ、ファイルに書き込む。

    名前指定時は単一テーブル、未指定時は AI がテーブル名も決定する。
    複数テーブル生成時、途中で失敗したら作成済みファイルをロールバックする。
    """
    logger.info("テーブル作成リクエスト: name=%s prompt_length=%d", name, len(prompt))
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
    logger.info("テーブル作成完了: tables=%s", [t[0] for t in tables])
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
    """既存テーブルの定義を AI に更新させる。"""
    logger.info("テーブル更新リクエスト: table=%s prompt_length=%d", name, len(prompt))
    _check_table_name(name)
    try:
        current_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    tsv = ai_service.generate_table_design(prompt, current_tsv)
    table_service.write_tsv(name, tsv)
    logger.info("テーブル更新完了: table=%s", name)
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


@router.post("/tables/{name}/physical")
def generate_physical(name: str, request: Request) -> Response:
    """論理設計から物理設計を AI に生成させる。"""
    logger.info("物理設計生成リクエスト: table=%s", name)
    _check_table_name(name)
    try:
        logical_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err

    logical_md = table_service.read_markdown(name) or ""

    common_rules: str | None = None
    index_md_path = get_data_dir() / "index.md"
    if index_md_path.exists():
        common_rules = index_md_path.read_text(encoding="utf-8")

    physical_md, physical_tsv, physical_doa = ai_service.generate_physical_design(
        name=name,
        logical_md=logical_md,
        logical_tsv=logical_tsv,
        common_rules=common_rules,
    )

    table_service.write_physical_tsv(name, physical_tsv)
    table_service.write_physical_doa_tsv(name, physical_doa)
    table_service.write_physical_markdown(name, physical_md)

    logger.info("物理設計生成完了: table=%s", name)
    redirect_url = f"/tables/{name}/physical"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    """テーブルの TSV と markdown を削除し、インデックスを再構築する。"""
    _check_table_name(name)
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
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
    """テーブル一覧再構築の SSE エンドポイント。"""
    return await _sse_rebuild(table_service.rebuild_index)


@router.get("/sse/rebuild-er")
async def sse_rebuild_er() -> StreamingResponse:
    """ER 図再構築の SSE エンドポイント。"""
    return await _sse_rebuild(table_service.rebuild_er_diagram_file)
