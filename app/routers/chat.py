import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import chat_service
from app.toon_io import read_index_toon, read_toon, serialize_table_toon

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/chat/history")
def chat_history() -> dict:
    """会話履歴を返す。

    Returns:
        メッセージリストを含む辞書。
    """
    conv = chat_service.load_conversation()
    return {"messages": [m.model_dump() for m in conv.messages]}


@router.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket) -> None:
    """チャット用 WebSocket エンドポイント。

    クライアントからの message/reset を受け付け、
    AI のストリーミング応答と content_updated 通知を返す。
    """
    await ws.accept()
    logger.info("WebSocket 接続")
    try:
        while True:
            data = await ws.receive_json()
            match data.get("type"):
                case "message":
                    await _handle_message(ws, data.get("content", ""))
                case "reset":
                    await _handle_reset(ws)
                case _:
                    await ws.send_json({"type": "error", "message": "unknown type"})
    except WebSocketDisconnect:
        logger.info("WebSocket 切断")


async def _handle_message(ws: WebSocket, content: str) -> None:
    if not content.strip():
        await ws.send_json({"type": "error", "message": "メッセージが空です"})
        return

    conv = chat_service.load_conversation()
    chat_service.add_user_message(conv, content)

    index = read_index_toon()
    relevant = await asyncio.to_thread(chat_service.identify_relevant_tables, content, index)

    context_toon = ""
    for name in relevant:
        try:
            doc = read_toon(name)
            context_toon += serialize_table_toon(doc) + "\n\n"
        except FileNotFoundError:
            logger.warning("関連テーブルが見つからない: table=%s", name)

    full_response = ""
    async for chunk in chat_service.generate_response_stream(conv, context_toon):
        full_response += chunk
        await ws.send_json({"type": "stream", "content": chunk})

    toon_blocks = chat_service.extract_toon_blocks(full_response)
    actions = await asyncio.to_thread(chat_service.apply_table_actions, toon_blocks, index)

    conv = chat_service.load_conversation()
    chat_service.add_assistant_message(conv, full_response, actions)

    await ws.send_json(
        {
            "type": "stream_end",
            "content": full_response,
            "actions": [a.model_dump() for a in actions],
        }
    )

    if actions:
        await ws.send_json({"type": "content_updated"})


async def _handle_reset(ws: WebSocket) -> None:
    conv = chat_service.reset_conversation()
    await ws.send_json({"type": "history", "messages": []})
    logger.info("チャットリセット: conv=%s", conv.id)
