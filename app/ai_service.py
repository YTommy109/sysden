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


def create_table_design(
    prompt: str,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> list[ToonDocument]:
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計生成スキップ (テストモード)")
        return [parse_table_toon(_STUB_CORE_TOON)]

    logger.info("AI コア設計生成開始: prompt_length=%d", len(prompt))
    config = _load_prompts()["core_create"]
    user_message = config["user_template"].format(
        rules="\n".join(f"- {r}" for r in rules) if rules else "なし",
        existing_tables=_format_existing_tables(existing_tables),
        prompt=prompt,
    )

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
        logger.exception("AI コア設計生成失敗")
        raise
    content = response.choices[0].message.content or ""
    tables = parse_toon_tables(content)
    logger.info("AI コア設計生成完了: tables=%d", len(tables))
    return tables


def update_table_design(
    prompt: str,
    current: ToonDocument,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> ToonDocument:
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計更新スキップ (テストモード)")
        return parse_table_toon(_STUB_CORE_TOON)

    logger.info("AI コア設計更新開始: table=%s", current.meta.physical_name)
    config = _load_prompts()["core_update"]
    user_message = config["user_template"].format(
        current_core=serialize_table_toon(current),
        rules="\n".join(f"- {r}" for r in rules) if rules else "なし",
        existing_tables=_format_existing_tables(existing_tables),
        prompt=prompt,
    )

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
        logger.exception("AI コア設計更新失敗: table=%s", current.meta.physical_name)
        raise
    content = response.choices[0].message.content or ""
    result = parse_table_toon(content)
    logger.info("AI コア設計更新完了: table=%s", current.meta.physical_name)
    return result
