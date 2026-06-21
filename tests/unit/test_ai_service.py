import logging

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


def test_AI生成でOpenAIが呼ばれる(mock_openai: list[dict]) -> None:
    # Arrange — fixture がモックを注入済み

    # Act
    result = ai_service.generate_table_design("ユーザーテーブル")

    # Assert
    assert "column_name" in result
    assert "id" in result
    assert len(mock_openai) == 1


def test_更新モードで現在のTSVがプロンプトに含まれる(mock_openai: list[dict]) -> None:
    # Arrange
    current = "column_name\ttype\n"

    # Act
    ai_service.generate_table_design("カラムを追加", current)

    # Assert
    msgs = mock_openai[0]["messages"]
    assert any("現在のテーブル定義" in m["content"] for m in msgs)


def test_APIキー未設定でValueError(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Act & Assert
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        ai_service.get_client()


def test_単一テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_複数テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_テストモードでスタブを返す(monkeypatch: pytest.MonkeyPatch) -> None:
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


class TestAiServiceLogging:
    """AI サービスのログ出力検証。"""

    def test_生成開始と完了がログ出力される(
        self, mock_openai: list[dict], caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange — fixture がモックを注入済み

        # Act
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.generate_table_design("ユーザーテーブル")

        # Assert
        assert "AI テーブル設計生成開始: mode=create" in caplog.text
        assert "AI テーブル設計生成完了: mode=create" in caplog.text

    def test_更新モードのログにupdateが含まれる(
        self, mock_openai: list[dict], caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        current = "column_name\ttype\n"

        # Act
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.generate_table_design("カラムを追加", current)

        # Assert
        assert "mode=update" in caplog.text

    def test_テーブル作成の開始と完了がログ出力される(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        fake = make_fake_openai_client(tsv=SINGLE_TABLE_RESPONSE)
        monkeypatch.setattr(ai_service, "get_client", lambda: fake)

        # Act
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.create_table_design("ユーザーテーブルを作って")

        # Assert
        assert "AI テーブル作成開始" in caplog.text
        assert "AI テーブル作成完了: tables=1" in caplog.text

    def test_テストモードのログ出力(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

        # Act
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.generate_table_design("テスト")

        # Assert
        assert "テストモード" in caplog.text


class TestParseMultiTableResponse:
    """_parse_multi_table_response のユニットテスト。"""

    def test_単一テーブルをパースする(self) -> None:
        # Act
        result = ai_service._parse_multi_table_response(SINGLE_TABLE_RESPONSE)

        # Assert
        assert len(result) == 1
        name, tsv, md = result[0]
        assert name == "users"
        assert "id\tUUID" in tsv
        assert "![[users.tsv]]" in md

    def test_複数テーブルをパースする(self) -> None:
        # Act
        result = ai_service._parse_multi_table_response(MULTI_TABLE_RESPONSE)

        # Assert
        assert len(result) == 2
        assert result[0][0] == "users"
        assert result[1][0] == "orders"
        assert "![[users.tsv]]" in result[0][2]
        assert "![[orders.tsv]]" in result[1][2]

    def test_前後の空白を除去する(self) -> None:
        # Arrange
        text = (
            "\n\n[users]\ncolumn_name\ttype\nid\tUUID\n\n[users.md]\n# users\n\n![[users.tsv]]\n\n"
        )

        # Act
        result = ai_service._parse_multi_table_response(text)

        # Assert
        assert len(result) == 1
        assert result[0][0] == "users"

    def test_空レスポンスでValueError(self) -> None:
        # Act & Assert
        with pytest.raises(ValueError, match="テーブル定義"):
            ai_service._parse_multi_table_response("")

    def test_セクションヘッダーなしでValueError(self) -> None:
        # Act & Assert
        with pytest.raises(ValueError, match="テーブル定義"):
            ai_service._parse_multi_table_response("column_name\ttype\nid\tUUID\n")


def test_generate_physical_design_テストモードでスタブを返す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: テストモードが有効
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

    # When: 物理設計を生成する
    md, tsv, doa = ai_service.generate_physical_design(
        name="users",
        logical_md="# ユーザー\n\n## テーブル設計\n\n![[users.tsv]]",
        logical_tsv="column_name\ttype\nid\tUUID\n",
    )

    # Then: スタブが返る
    assert "physical_users.tsv" in md
    assert "column_name\t" in tsv
    assert "column_name\t" in doa


def test_parse_physical_response_正常系() -> None:
    # Given: 3 セクションを含むレスポンス
    content = (
        "[table]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n"
        "\n"
        "[doa]\n"
        "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\n"
        "id\tUUID\tYES\t\t\t\t\n"
        "\n"
        "[markdown]\n"
        "# 物理設計\n\n## テーブル定義\n\n![[physical_users.tsv]]\n"
    )

    # When: パースする
    md, tsv, doa = ai_service._parse_physical_response(content)

    # Then: 各セクションが正しく抽出される
    assert "physical_users.tsv" in md
    assert "uuid" in tsv
    assert "UUID" in doa


def test_parse_physical_response_コードブロック記号を除去する() -> None:
    # Given: セクション内容がバッククォートで囲まれたレスポンス
    content = (
        "[table]\n"
        "```\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tuuid\tNO\tYES\tYES\tgen_random_uuid()\t主キー\n"
        "```\n"
        "\n"
        "[doa]\n"
        "```tsv\n"
        "column_name\tpython_type\trequired\tmin\tmax\tmax_length\tdescription\n"
        "id\tUUID\tYES\t\t\t\t\n"
        "```\n"
        "\n"
        "[markdown]\n"
        "```markdown\n"
        "# 物理設計\n\n## テーブル定義\n\n![[physical_users.tsv]]\n"
        "```\n"
    )

    # When: パースする
    md, tsv, doa = ai_service._parse_physical_response(content)

    # Then: バッククォートが除去されて正しくパースされる
    assert "```" not in tsv
    assert "```" not in doa
    assert "```" not in md
    assert "column_name" in tsv
    assert "UUID" in doa
    assert "physical_users.tsv" in md


def test_parse_physical_response_セクション不足でエラー() -> None:
    # Given: doa セクションが欠けたレスポンス
    content = "[table]\ncolumn_name\ttype\nid\tuuid\n\n[markdown]\n# 物理設計\n"

    # When/Then: ValueError が発生する
    with pytest.raises(ValueError, match="セクションが不足"):
        ai_service._parse_physical_response(content)
