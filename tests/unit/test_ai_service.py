import pytest

from app import ai_service
from tests.conftest import make_fake_openai_client

MULTI_TABLE_RESPONSE = (
    "[users]\n"
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    "\n"
    "[users.md]\n"
    "# users テーブル\n"
    "\n"
    "ユーザー情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[users.tsv]]\n"
    "\n"
    "[orders]\n"
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    "user_id\tUUID\tNO\tNO\tNO\t\t注文者\n"
    "\n"
    "[orders.md]\n"
    "# orders テーブル\n"
    "\n"
    "注文情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[orders.tsv]]\n"
)

SINGLE_TABLE_RESPONSE = (
    "[users]\n"
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    "\n"
    "[users.md]\n"
    "# users テーブル\n"
    "\n"
    "ユーザー情報を管理する。\n"
    "\n"
    "## テーブル設計\n"
    "\n"
    "![[users.tsv]]\n"
)


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


def test_create_table_design_single_table(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(tsv=SINGLE_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design("ユーザーテーブルを作って")

    # Assert
    assert len(tables) == 1
    name, tsv, md = tables[0]
    assert name == "users"
    assert "column_name" in tsv
    assert "![[users.tsv]]" in md


def test_create_table_design_multiple_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(tsv=MULTI_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design("ユーザーと注文テーブルを作って")

    # Assert
    assert len(tables) == 2
    assert tables[0][0] == "users"
    assert tables[1][0] == "orders"
    assert "user_id" in tables[1][1]
    assert "![[orders.tsv]]" in tables[1][2]


def test_create_table_design_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

    # Act
    tables = ai_service.create_table_design("何でも")

    # Assert
    assert len(tables) == 1
    name, tsv, md = tables[0]
    assert isinstance(name, str)
    assert len(name) > 0
    assert "column_name" in tsv
    assert f"![[{name}.tsv]]" in md


class TestParseMultiTableResponse:
    """_parse_multi_table_response のユニットテスト。"""

    def test_single_table(self) -> None:
        # Act
        result = ai_service._parse_multi_table_response(SINGLE_TABLE_RESPONSE)

        # Assert
        assert len(result) == 1
        name, tsv, md = result[0]
        assert name == "users"
        assert "id\tUUID" in tsv
        assert "![[users.tsv]]" in md

    def test_multiple_tables(self) -> None:
        # Act
        result = ai_service._parse_multi_table_response(MULTI_TABLE_RESPONSE)

        # Assert
        assert len(result) == 2
        assert result[0][0] == "users"
        assert result[1][0] == "orders"
        assert "![[users.tsv]]" in result[0][2]
        assert "![[orders.tsv]]" in result[1][2]

    def test_strips_whitespace(self) -> None:
        # Arrange
        text = (
            "\n\n[users]\ncolumn_name\ttype\nid\tUUID\n\n[users.md]\n# users\n\n![[users.tsv]]\n\n"
        )

        # Act
        result = ai_service._parse_multi_table_response(text)

        # Assert
        assert len(result) == 1
        assert result[0][0] == "users"

    def test_empty_response_raises(self) -> None:
        # Act & Assert
        with pytest.raises(ValueError, match="テーブル定義"):
            ai_service._parse_multi_table_response("")

    def test_no_section_header_raises(self) -> None:
        # Act & Assert
        with pytest.raises(ValueError, match="テーブル定義"):
            ai_service._parse_multi_table_response("column_name\ttype\nid\tUUID\n")
