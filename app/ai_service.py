import os
from pathlib import Path

import yaml
from openai import OpenAI

_STUB_TSV = (
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
)

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
        user_message = config["user_update_template"].format(
            current_tsv=current_tsv, prompt=prompt
        )

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
