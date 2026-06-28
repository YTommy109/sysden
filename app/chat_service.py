import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from app import ai_service, symbol_service, table_service
from app.config import get_data_dir
from app.derive_service import derive_all
from app.models import ChatAction, ChatMessage, Conversation, IndexDocument, TableSummary
from app.toon_io import parse_toon_tables, read_index_toon

logger = logging.getLogger(__name__)

_META_LINE_RE = re.compile(r"^meta:\s*$", re.MULTILINE)
_PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "ai_prompts.yaml"
_STREAM_TRUE: Literal[True] = True

_STUB_CHAT_RESPONSE = """\
テスト用テーブルを作成します。

meta:
  logical_name: スタブ
  physical_name: stub_table
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー

以上です。"""


def _load_prompts() -> dict:
    with _PROMPTS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _format_existing_tables(tables: list[TableSummary]) -> str:
    if not tables:
        return "なし"
    return "\n".join(f"{t.symbol}: {t.logical_name} ({t.name})" for t in tables)


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


def extract_toon_blocks(text: str) -> list[str]:
    """応答テキストから TOON ブロック（meta: + columns:）を抽出する。

    Args:
        text: AI の応答テキスト。

    Returns:
        抽出された TOON ブロックのリスト。
    """
    matches = list(_META_LINE_RE.finditer(text))
    if not matches:
        return []

    blocks: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if "columns[" in block:
            blocks.append(block)
    return blocks


def identify_relevant_tables(prompt: str, index: IndexDocument) -> list[str]:
    """Stage 1: ユーザーの依頼に必要なテーブルを特定する。

    Args:
        prompt: ユーザーの依頼テキスト。
        index: インデックスドキュメント。

    Returns:
        関連テーブルの physical_name リスト。
    """
    if not index.tables:
        return []

    config = _load_prompts()["chat_identify"]
    user_message = config["user_template"].format(
        existing_tables=_format_existing_tables(index.tables),
        prompt=prompt,
    )
    client = ai_service.get_client()
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": config["system"]},
            {"role": "user", "content": user_message},
        ],
        temperature=config["temperature"],
    )
    content = response.choices[0].message.content or "[]"
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Stage 1 JSON パース失敗: content=%s", content)
        return []
    if not isinstance(result, list):
        return []
    logger.info("関連テーブル特定: tables=%s", result)
    return result


def apply_table_actions(toon_blocks: list[str], index: IndexDocument) -> list[ChatAction]:
    """TOON ブロックからテーブルを作成/更新し、実行アクションを返す。

    Args:
        toon_blocks: AI 応答から抽出した TOON テキストのリスト。
        index: 現在のインデックスドキュメント。

    Returns:
        実行されたアクションのリスト。
    """
    actions: list[ChatAction] = []
    existing_names = {t.name for t in index.tables}

    for block in toon_blocks:
        docs = parse_toon_tables(block)
        for doc in docs:
            name = doc.meta.physical_name
            if name in existing_names:
                current = table_service.get_table(name)
                doc = doc.model_copy(
                    update={"meta": doc.meta.model_copy(update={"symbol": current.meta.symbol})}
                )
                doc = derive_all(doc)
                table_service.save_table(name, doc)
                actions.append(ChatAction(type="update_table", table_name=name))
                logger.info("テーブル更新: table=%s", name)
            else:
                sym = symbol_service.allocate_table_symbol()
                doc = doc.model_copy(update={"meta": doc.meta.model_copy(update={"symbol": sym})})
                doc = derive_all(doc)
                table_service.save_table(name, doc)
                actions.append(ChatAction(type="create_table", table_name=name))
                logger.info("テーブル作成: table=%s symbol=%s", name, sym)

    if actions:
        table_service.rebuild_index()
    return actions


async def generate_response_stream(
    conv: Conversation,
    context_toon: str = "",
) -> AsyncGenerator[str]:
    """Stage 2: 会話履歴からストリーミング応答を生成する。

    Args:
        conv: 現在の会話。
        context_toon: 関連テーブルの TOON コンテキスト。

    Yields:
        応答テキストのチャンク。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("チャット応答生成スキップ (テストモード)")
        for char in _STUB_CHAT_RESPONSE:
            yield char
            await asyncio.sleep(0)
        return

    config = _load_prompts()["chat"]
    messages: list[Any] = [{"role": "system", "content": config["system"]}]

    if context_toon:
        messages.append(
            {
                "role": "system",
                "content": f"関連テーブルの現在の設計:\n{context_toon}",
            }
        )

    index = read_index_toon()
    if index.rules:
        rules_text = "\n".join(f"- {r}" for r in index.rules)
        messages.append(
            {
                "role": "system",
                "content": f"共通ルール:\n{rules_text}",
            }
        )

    for msg in conv.messages:
        messages.append({"role": msg.role, "content": msg.content})

    client = ai_service.get_client()
    logger.info("チャット応答生成開始: conv=%s messages=%d", conv.id, len(messages))
    stream = client.chat.completions.create(
        model=config["model"],
        messages=messages,
        temperature=config["temperature"],
        stream=_STREAM_TRUE,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
