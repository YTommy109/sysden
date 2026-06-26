from pathlib import Path
from types import SimpleNamespace

import pytest

SAMPLE_TOON = """\
meta:
  symbol: TABLE_0001
  logical_name: ユーザー
  physical_name: users
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,,,主キー
"""

SAMPLE_CORE_TOON = """\
meta:
  logical_name: スタブ
  physical_name: stub_table
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー
"""


def make_fake_openai_client(
    response: str = SAMPLE_CORE_TOON,
    calls: list[dict] | None = None,
) -> SimpleNamespace:
    """OpenAI API 構造を模倣するスタブクライアントを生成する。"""

    def create(**kwargs: object) -> SimpleNamespace:
        if calls is not None:
            calls.append(kwargs)
        choice = SimpleNamespace(message=SimpleNamespace(content=response))
        return SimpleNamespace(choices=[choice])

    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


@pytest.fixture()
def sample_toon() -> str:
    """テスト用の最小限テーブル TOON。"""
    return SAMPLE_TOON


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全テストで一時データディレクトリと API キーを設定する。"""
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
