import logging

import pytest

from app import ai_service
from app.models import TableSummary, ToonDocument
from tests.conftest import SAMPLE_CORE_TOON, make_fake_openai_client

MULTI_TABLE_RESPONSE = """\
meta:
  logical_name: ユーザー
  physical_name: users
  description: ユーザー情報

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,

meta:
  logical_name: 注文
  physical_name: orders
  description: 注文情報

columns[2]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,注文ID,order_id,uuid,NO,YES,YES,gen_random_uuid(),,
  COLUMN_0002,注文者,user_id,uuid,NO,NO,NO,,NEW_1,
"""

SINGLE_TABLE_RESPONSE = SAMPLE_CORE_TOON


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """OpenAI クライアントをスタブに差し替え、API 呼び出しを記録する。"""
    calls: list[dict] = []
    monkeypatch.setattr(
        ai_service, "get_client", lambda: make_fake_openai_client(calls=calls)
    )
    return calls


def test_単一テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=SINGLE_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design(
        prompt="テストテーブルを作って", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 1
    assert tables[0].meta.physical_name == "stub_table"
    assert len(tables[0].columns) == 1


def test_複数テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=MULTI_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design(
        prompt="ユーザーと注文テーブルを作って", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 2
    assert tables[0].meta.physical_name == "users"
    assert tables[1].meta.physical_name == "orders"
    assert tables[1].columns[1].fk_target == "NEW_1"


def test_テーブル更新(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=SINGLE_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)
    from app.toon_io import parse_table_toon

    current = parse_table_toon(SINGLE_TABLE_RESPONSE)

    # Act
    result = ai_service.update_table_design(
        prompt="カラムを追加",
        current=current,
        rules=[],
        existing_tables=[],
    )

    # Assert
    assert isinstance(result, ToonDocument)
    assert result.meta.physical_name == "stub_table"


def test_更新モードで現在のコア設計がプロンプトに含まれる(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    calls: list[dict] = []
    fake = make_fake_openai_client(
        response=SINGLE_TABLE_RESPONSE, calls=calls
    )
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)
    from app.toon_io import parse_table_toon

    current = parse_table_toon(SINGLE_TABLE_RESPONSE)

    # Act
    ai_service.update_table_design(
        prompt="カラムを追加",
        current=current,
        rules=["ルール1"],
        existing_tables=[
            TableSummary(
                symbol="TABLE_0001",
                name="test",
                logical_name="テスト",
                description="",
            )
        ],
    )

    # Assert
    msgs = calls[0]["messages"]
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert "現在のコア設計" in user_msg["content"]
    assert "ルール1" in user_msg["content"]
    assert "TABLE_0001" in user_msg["content"]


def test_テストモードでスタブを返す(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

    # Act
    tables = ai_service.create_table_design(
        prompt="何でも", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 1
    assert tables[0].meta.physical_name == "stub_table"
    assert len(tables[0].columns) >= 1


def test_APIキー未設定でValueError(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Act & Assert
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        ai_service.get_client()


class TestAiServiceLogging:
    def test_生成開始と完了がログ出力される(
        self, mock_openai: list[dict], caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.create_table_design(
                prompt="テスト", rules=[], existing_tables=[]
            )
        assert "AI コア設計生成開始" in caplog.text
        assert "AI コア設計生成完了" in caplog.text

    def test_テストモードのログ出力(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("SYSDEN_TEST_MODE", "1")
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.create_table_design(
                prompt="テスト", rules=[], existing_tables=[]
            )
        assert "テストモード" in caplog.text
