import logging
import os
from pathlib import Path

import yaml
from openai import OpenAI

from app.models import TableSummary, ToonDocument
from app.toon_io import parse_table_toon, parse_toon_tables, serialize_table_toon

logger = logging.getLogger(__name__)

_STUB_CORE_TOON = """\
meta:
  logical_name: スタブ
  physical_name: stub_table
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー
"""

_PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "ai_prompts.yaml"


def _load_prompts() -> dict:
    with _PROMPTS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client() -> OpenAI:
    """OpenAI クライアントを生成する。

    Returns:
        設定済みの OpenAI クライアント。

    Raises:
        ValueError: OPENAI_API_KEY が未設定の場合。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY が設定されていません")
    return OpenAI(api_key=api_key)


def _format_existing_tables(tables: list[TableSummary]) -> str:
    if not tables:
        return "なし"
    lines: list[str] = []
    for t in tables:
        lines.append(f"{t.symbol}: {t.logical_name} ({t.name})")
    return "\n".join(lines)


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules) if rules else "なし"


def _call_openai(config_key: str, template_vars: dict[str, str], log_label: str) -> str:
    """OpenAI API を呼び出して応答テキストを返す。

    Args:
        config_key: ``ai_prompts.yaml`` 内のプロンプト設定キー。
        template_vars: ユーザーメッセージテンプレートに渡す変数。
        log_label: ログ出力に使う操作ラベル。

    Returns:
        API レスポンスのテキスト。
    """
    config = _load_prompts()[config_key]
    user_message = config["user_template"].format(**template_vars)
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": config["system"]},
                {"role": "user", "content": user_message},
            ],
            temperature=config["temperature"],
        )
    except Exception:
        logger.exception("%s失敗", log_label)
        raise
    return response.choices[0].message.content or ""


def create_table_design(
    prompt: str,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> list[ToonDocument]:
    """AI にコア設計（TOON）を新規生成させる。

    Args:
        prompt: ユーザーからの依頼テキスト。
        rules: 共通ルール一覧。
        existing_tables: 既存テーブルの要約リスト。

    Returns:
        生成された ToonDocument のリスト。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計生成スキップ (テストモード)")
        return [parse_table_toon(_STUB_CORE_TOON)]

    log_label = "AI コア設計生成"
    logger.info("%s開始: prompt_length=%d", log_label, len(prompt))
    content = _call_openai(
        "core_create",
        {
            "rules": _format_rules(rules),
            "existing_tables": _format_existing_tables(existing_tables),
            "prompt": prompt,
        },
        log_label,
    )
    tables = parse_toon_tables(content)
    logger.info("%s完了: tables=%d", log_label, len(tables))
    return tables


def update_table_design(
    prompt: str,
    current: ToonDocument,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> ToonDocument:
    """AI にコア設計（TOON）を更新させる。

    Args:
        prompt: ユーザーからの変更依頼テキスト。
        current: 更新対象の現在の ToonDocument。
        rules: 共通ルール一覧。
        existing_tables: 既存テーブルの要約リスト。

    Returns:
        更新された ToonDocument。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計更新スキップ (テストモード)")
        return parse_table_toon(_STUB_CORE_TOON)

    log_label = f"AI コア設計更新: table={current.meta.physical_name}"
    logger.info("%s開始", log_label)
    content = _call_openai(
        "core_update",
        {
            "current_core": serialize_table_toon(current),
            "rules": _format_rules(rules),
            "existing_tables": _format_existing_tables(existing_tables),
            "prompt": prompt,
        },
        log_label,
    )
    result = parse_table_toon(content)
    logger.info("%s完了", log_label)
    return result
