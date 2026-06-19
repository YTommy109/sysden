import pytest

from app import ai_service
from tests.conftest import make_fake_openai_client


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """OpenAI クライアントをスタブに差し替え、API 呼び出しを記録する。"""
    calls: list[dict] = []
    monkeypatch.setattr(ai_service, "get_client", lambda: make_fake_openai_client(calls=calls))
    return calls


def test_generate_table_design_calls_openai(mock_openai: list[dict]) -> None:
    # Arrange — fixture がモックを注入済み

    # Act
    result = ai_service.generate_table_design("ユーザーテーブル")

    # Assert
    assert "column_name" in result
    assert "id" in result
    assert len(mock_openai) == 1


def test_generate_table_design_includes_current_tsv(mock_openai: list[dict]) -> None:
    # Arrange
    current = "column_name\ttype\n"

    # Act
    ai_service.generate_table_design("カラムを追加", current)

    # Assert
    msgs = mock_openai[0]["messages"]
    assert any("現在のテーブル定義" in m["content"] for m in msgs)


def test_get_client_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Act & Assert
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        ai_service.get_client()
