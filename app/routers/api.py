import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from app import table_service
from app.templating import templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _rebuilding_response(request: Request, sse_url: str, target: str, label: str) -> Response:
    """SSE リビルド中のスピナー HTML を返す。"""
    return templates.TemplateResponse(
        request,
        "_spinner.html",
        {"sse_url": sse_url, "target": target, "label": label},
    )


@router.post("/tables")
def create_table(
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    """AI にテーブル設計を依頼し、結果を保存する。

    Args:
        request: FastAPI リクエスト。
        prompt: ユーザーからの依頼テキスト。

    Returns:
        htmx リクエストなら HX-Redirect ヘッダー、それ以外は 303 リダイレクト。
    """
    logger.info("テーブル作成リクエスト: prompt_length=%d", len(prompt))
    try:
        names = table_service.create_tables_from_ai(prompt)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    except FileExistsError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err
    redirect_url = f"/tables/{names[0]}" if len(names) == 1 else "/"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    """AI に既存テーブルの設計更新を依頼し、結果を保存する。

    Args:
        name: 更新対象のテーブル名。
        request: FastAPI リクエスト。
        prompt: ユーザーからの変更依頼テキスト。

    Returns:
        htmx リクエストなら HX-Redirect ヘッダー、それ以外は 303 リダイレクト。
    """
    logger.info("テーブル更新リクエスト: table=%s", name)
    try:
        table_service.update_table_from_ai(name, prompt)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    redirect_url = f"/tables/{name}"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/rebuild-index-tables")
def rebuild_index_tables(request: Request) -> Response:
    """テーブル一覧のインデックスを再構築する。

    htmx リクエストの場合は SSE でスピナーを表示しながら非同期で実行する。

    Args:
        request: FastAPI リクエスト。

    Returns:
        htmx なら SSE 接続付き HTML、それ以外は 303 リダイレクト。
    """
    if request.headers.get("HX-Request"):
        return _rebuilding_response(
            request, "/api/sse/rebuild-index", "#index-body", "テーブル一覧の再作成"
        )
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.post("/rebuild-er-diagram")
def rebuild_er_diagram(request: Request) -> Response:
    """ER 図を再構築する。

    htmx リクエストの場合は SSE でスピナーを表示しながら非同期で実行する。

    Args:
        request: FastAPI リクエスト。

    Returns:
        htmx なら SSE 接続付き HTML、それ以外は 303 リダイレクト。
    """
    if request.headers.get("HX-Request"):
        return _rebuilding_response(request, "/api/sse/rebuild-er", "#er-diagram", "ER 図の再作成")
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    """テーブルを削除してインデックスを再構築する。

    Args:
        name: 削除対象のテーブル名。

    Returns:
        削除結果の JSON（status, name）。
    """
    try:
        table_service.delete_table(name)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
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
            logger.exception("SSE リビルド失敗: func=%s", getattr(func, "__name__", func))
            yield "event: error\ndata: rebuild failed\n\n"
            return
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
    """インデックス再構築の SSE ストリームを返す。"""
    return await _sse_rebuild(table_service.rebuild_index)


@router.get("/sse/rebuild-er")
async def sse_rebuild_er() -> StreamingResponse:
    """ER 図再構築の SSE ストリームを返す。"""
    return await _sse_rebuild(table_service.rebuild_index)
