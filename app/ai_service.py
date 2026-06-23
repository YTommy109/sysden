import logging
import os
import re
from pathlib import Path

import yaml
from openai import OpenAI

logger = logging.getLogger(__name__)

_STUB_TSV = (
    "symbol\tlogical_name\tphysical_name\ttype\tnullable\tpk\tunique\tdefault\tfk_target\tdescription\n"
    "COLUMN_0001\t識別子\tid\tUUID\tNO\tYES\tYES\t\t\t主キー\n"
)

_STUB_MD = "# スタブ\n\n## 概要\n\nテスト用テーブル。\n\n## テーブル設計\n\n![[stub_table.tsv]]\n"


_SECTION_RE = re.compile(r"^\[([^\]]+)\]$")
_CODE_FENCE_RE = re.compile(r"^```\w*$")

_STUB_PHYSICAL_TSV = (
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n"
)

_STUB_PHYSICAL_DOA_TSV = (
    "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\nid\tUUID\tYES\t\t\t\t\n"
)

_STUB_PHYSICAL_MD = (
    "# 物理設計\n\n## テーブル定義\n\n![[physical_stub_table.tsv]]\n\n"
    "## DoA バリデーション\n\n![[physical_stub_table_doa.tsv]]\n"
)

_PHYSICAL_SECTION_RE = re.compile(r"^\[(table|doa|markdown)\]$")

_PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "ai_prompts.yaml"


def _load_prompts() -> dict:
    """プロンプト定義ファイルを読み込む。

    Returns:
        YAML からパースしたプロンプト定義辞書。
    """
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


def _parse_multi_table_response(content: str) -> list[tuple[str, str, str]]:
    """``[table_name]`` セクション形式のレスポンスをパースする。

    TSV セクション（``[name]``）と markdown セクション（``[name.md]``）を
    テーブルごとにまとめて返す。

    Args:
        content: AI が返した ``[name]\\nTSV...\\n[name.md]\\nmarkdown...`` 形式のテキスト。

    Returns:
        ``(テーブル名, TSV 文字列, markdown 文字列)`` のリスト。

    Raises:
        ValueError: TSV セクションが 1 つも見つからない場合。
    """
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        m = _SECTION_RE.match(line.strip())
        if m:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip() + "\n"
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip() + "\n"

    tsv_names = [k for k in sections if not k.endswith(".md")]
    if not tsv_names:
        raise ValueError("テーブル定義が見つかりません")

    result: list[tuple[str, str, str]] = []
    for name in tsv_names:
        tsv = sections[name]
        md = sections.get(f"{name}.md", "")
        result.append((name, tsv, md))

    return result


def generate_table_design(
    prompt: str,
    current_tsv: str | None = None,
    table_symbol: str | None = None,
) -> str:
    """AI にテーブル設計（TSV）を生成または更新させる。

    Args:
        prompt: ユーザーからの依頼テキスト。
        current_tsv: 既存のカラム定義 TSV。指定時は更新モードで動作する。
        table_symbol: 更新対象テーブルのシンボル（例: TABLE_0001）。

    Returns:
        生成されたカラム定義の TSV 文字列。
    """
    mode = "update" if current_tsv else "create"
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI テーブル設計生成スキップ (テストモード): mode=%s", mode)
        return _STUB_TSV

    logger.info("AI テーブル設計生成開始: mode=%s prompt_length=%d", mode, len(prompt))
    config = _load_prompts()["table_design"]

    user_message = prompt
    if current_tsv:
        user_message = config["user_update_template"].format(
            current_tsv=current_tsv,
            prompt=prompt,
            table_symbol=table_symbol or "",
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
        logger.exception("AI テーブル設計生成失敗: mode=%s", mode)
        raise
    result = response.choices[0].message.content or ""
    logger.info("AI テーブル設計生成完了: mode=%s result_length=%d", mode, len(result))
    return result


def create_table_design(prompt: str, next_table_id: int = 1) -> list[tuple[str, str, str]]:
    """AI にテーブル名とカラム定義（TSV）と説明（markdown）を生成させる。

    Args:
        prompt: ユーザーからの依頼テキスト。
        next_table_id: 採番開始番号。AI はこの番号から TABLE_XXXX シンボルを生成する。

    Returns:
        ``(シンボル, TSV 文字列, markdown 文字列)`` のリスト。シンボルは TABLE_XXXX 形式。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI テーブル作成スキップ (テストモード)")
        symbol = f"TABLE_{next_table_id:04d}"
        return [(symbol, _STUB_TSV, _STUB_MD)]

    logger.info("AI テーブル作成開始: prompt_length=%d", len(prompt))
    config = _load_prompts()["table_create"]
    system_msg = config["system"].format(next_table_id=next_table_id)
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=config["temperature"],
        )
        content = response.choices[0].message.content or ""
        tables = _parse_multi_table_response(content)
    except Exception:
        logger.exception("AI テーブル作成失敗")
        raise
    logger.info("AI テーブル作成完了: tables=%d", len(tables))
    return tables


def _parse_physical_response(content: str) -> tuple[str, str, str]:
    """物理設計レスポンスの [table]/[doa]/[markdown] セクションをパースする。

    Returns:
        (markdown, table_tsv, doa_tsv) のタプル。

    Raises:
        ValueError: 必須セクションが欠けている場合。
    """
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []

    for line in content.splitlines():
        m = _PHYSICAL_SECTION_RE.match(line.strip())
        if m:
            if current is not None:
                sections[current] = "\n".join(lines).strip() + "\n"
            current = m.group(1)
            lines = []
        elif current is not None:
            if not _CODE_FENCE_RE.match(line.strip()):
                lines.append(line)

    if current is not None:
        sections[current] = "\n".join(lines).strip() + "\n"

    missing = {"table", "doa", "markdown"} - sections.keys()
    if missing:
        raise ValueError(f"物理設計のセクションが不足しています: {missing}")

    return sections["markdown"], sections["table"], sections["doa"]


def generate_physical_design(
    name: str,
    logical_md: str,
    logical_tsv: str,
    common_rules: str | None = None,
) -> tuple[str, str, str]:
    """AI に物理設計を生成させる。

    Args:
        name: テーブル名。
        logical_md: 論理設計の markdown。
        logical_tsv: 論理設計の TSV。
        common_rules: 共通ルール（index.md の内容）。

    Returns:
        (physical_md, physical_tsv, physical_doa_tsv) のタプル。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI 物理設計生成スキップ (テストモード)")
        stub_md = _STUB_PHYSICAL_MD.replace("stub_table", name)
        return stub_md, _STUB_PHYSICAL_TSV, _STUB_PHYSICAL_DOA_TSV

    logger.info("AI 物理設計生成開始: table=%s", name)
    config = _load_prompts()["physical_design"]
    user_message = config["user_template"].format(
        name=name,
        logical_md=logical_md,
        logical_tsv=logical_tsv,
        common_rules=common_rules or "なし",
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
        logger.exception("AI 物理設計生成失敗: table=%s", name)
        raise
    content = response.choices[0].message.content or ""
    result = _parse_physical_response(content)
    logger.info("AI 物理設計生成完了: table=%s", name)
    return result
