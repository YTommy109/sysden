import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_data_dir
from app.models import ChatAction, ChatMessage, Conversation

logger = logging.getLogger(__name__)


def _chat_dir() -> Path:
    d = get_data_dir() / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _conversation_path() -> Path:
    return _chat_dir() / "conversation.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_conversation() -> Conversation:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    return Conversation(id=f"conv_{ts}", created_at=_now_iso())


def load_conversation() -> Conversation:
    """会話を JSON ファイルから読み込む。ファイルがなければ新規作成する。

    Returns:
        現在の Conversation。
    """
    path = _conversation_path()
    if not path.exists():
        conv = _new_conversation()
        save_conversation(conv)
        return conv
    data = json.loads(path.read_text(encoding="utf-8"))
    return Conversation.model_validate(data)


def save_conversation(conv: Conversation) -> None:
    """会話を JSON ファイルに保存する。

    Args:
        conv: 保存する Conversation。
    """
    path = _conversation_path()
    path.write_text(conv.model_dump_json(indent=2), encoding="utf-8")


def add_user_message(conv: Conversation, content: str) -> ChatMessage:
    """ユーザーメッセージを追加して保存する。

    Args:
        conv: 現在の会話。
        content: メッセージ本文。

    Returns:
        追加された ChatMessage。
    """
    msg = ChatMessage(role="user", content=content, timestamp=_now_iso())
    conv.messages.append(msg)
    save_conversation(conv)
    logger.info("ユーザーメッセージ追加: conv=%s length=%d", conv.id, len(content))
    return msg


def add_assistant_message(
    conv: Conversation, content: str, actions: list[ChatAction] | None = None
) -> ChatMessage:
    """アシスタントメッセージを追加して保存する。

    Args:
        conv: 現在の会話。
        content: メッセージ本文。
        actions: 実行されたアクションのリスト。

    Returns:
        追加された ChatMessage。
    """
    msg = ChatMessage(
        role="assistant",
        content=content,
        timestamp=_now_iso(),
        actions=actions or [],
    )
    conv.messages.append(msg)
    save_conversation(conv)
    logger.info("アシスタントメッセージ追加: conv=%s actions=%d", conv.id, len(msg.actions))
    return msg


def reset_conversation() -> Conversation:
    """会話をリセットして新しい会話を返す。

    Returns:
        新しい Conversation。
    """
    conv = _new_conversation()
    save_conversation(conv)
    logger.info("会話リセット: new_conv=%s", conv.id)
    return conv
