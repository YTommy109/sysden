import os
import re
from pathlib import Path

import yaml
from openai import OpenAI

_STUB_TSV = (
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
)

_STUB_MD = "# スタブ\n\n## 概要\n\nテスト用テーブル。\n\n## テーブル設計\n\n![[stub_table.tsv]]\n"


_SECTION_RE = re.compile(r"^\[([^\]]+)\]$")

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


def generate_table_design(prompt: str, current_tsv: str | None = None) -> str:
    """AI にテーブル設計（TSV）を生成または更新させる。

    Args:
        prompt: ユーザーからの依頼テキスト。
        current_tsv: 既存のカラム定義 TSV。指定時は更新モードで動作する。

    Returns:
        生成されたカラム定義の TSV 文字列。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        return _STUB_TSV

    config = _load_prompts()["table_design"]

    user_message = prompt
    if current_tsv:
        user_message = config["user_update_template"].format(current_tsv=current_tsv, prompt=prompt)

    client = get_client()
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": config["system"]},
            {"role": "user", "content": user_message},
        ],
        temperature=config["temperature"],
    )
    return response.choices[0].message.content or ""


def create_table_design(prompt: str) -> list[tuple[str, str, str]]:
    """AI にテーブル名とカラム定義（TSV）と説明（markdown）を生成させる。

    Args:
        prompt: ユーザーからの依頼テキスト。

    Returns:
        ``(テーブル名, TSV 文字列, markdown 文字列)`` のリスト。
    """
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        return [("stub_table", _STUB_TSV, _STUB_MD)]

    config = _load_prompts()["table_create"]
    client = get_client()
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": config["system"]},
            {"role": "user", "content": prompt},
        ],
        temperature=config["temperature"],
    )
    content = response.choices[0].message.content or ""
    return _parse_multi_table_response(content)
