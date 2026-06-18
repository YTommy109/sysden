import os
from typing import Optional

from openai import OpenAI

SYSTEM_PROMPT = """あなたはデータベーステーブル設計のアシスタントです。
ユーザーの依頼に応じて、以下のヘッダーを持つ TSV 形式でテーブルのカラム定義を出力してください。

ヘッダー（タブ区切り、必須）:
column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription

出力規則:
- ヘッダー行 + データ行のみを出力。説明文・コードブロック記号は不要
- nullable, pk, unique は YES または NO で記述
- default が存在しない場合は空文字（タブのみ）
- 日本語の説明を description に記載する
"""


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY が設定されていません")
    return OpenAI(api_key=api_key)


def generate_table_design(prompt: str, current_tsv: Optional[str] = None) -> str:
    """AI にテーブル設計（TSV）を生成または更新させる。"""
    user_message = prompt
    if current_tsv:
        user_message = f"現在のテーブル定義:\n{current_tsv}\n\n依頼: {prompt}"

    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
