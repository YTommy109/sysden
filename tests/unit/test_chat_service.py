import asyncio
import logging

import pytest

from app import chat_service
from app.models import ChatAction, IndexDocument, TableSummary
from tests.conftest import SAMPLE_CORE_TOON, make_fake_openai_client


class TestConversationPersistence:
    def test_新しい会話を作成する(self) -> None:
        # Arrange & Act
        conv = chat_service.reset_conversation()

        # Assert
        assert conv.id.startswith("conv_")
        assert conv.messages == []
        assert conv.created_at != ""

    def test_会話を保存して読み込む(self) -> None:
        # Arrange
        conv = chat_service.reset_conversation()
        chat_service.add_user_message(conv, "テスト")

        # Act
        loaded = chat_service.load_conversation()

        # Assert
        assert loaded.id == conv.id
        assert len(loaded.messages) == 1
        assert loaded.messages[0].role == "user"
        assert loaded.messages[0].content == "テスト"

    def test_アシスタントメッセージにアクションを記録する(self) -> None:
        # Arrange
        conv = chat_service.reset_conversation()
        actions = [ChatAction(type="create_table", table_name="TABLE_0001")]

        # Act
        msg = chat_service.add_assistant_message(conv, "作成しました", actions)

        # Assert
        assert msg.role == "assistant"
        assert len(msg.actions) == 1
        assert msg.actions[0].table_name == "TABLE_0001"

    def test_リセットで新しい会話になる(self) -> None:
        # Arrange
        conv = chat_service.reset_conversation()
        chat_service.add_user_message(conv, "古いメッセージ")

        # Act
        new_conv = chat_service.reset_conversation()

        # Assert
        assert new_conv.id != conv.id
        assert new_conv.messages == []

    def test_ファイルがなければ新規作成する(self) -> None:
        # Arrange & Act
        conv = chat_service.load_conversation()

        # Assert
        assert conv.id.startswith("conv_")
        assert conv.messages == []

    def test_リセット時にログを出力する(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange & Act
        with caplog.at_level(logging.INFO):
            conv = chat_service.reset_conversation()

        # Assert
        assert f"new_conv={conv.id}" in caplog.text


class TestToonExtraction:
    def test_応答テキストからTOONブロックを抽出する(self) -> None:
        # Arrange
        text = (
            "ユーザーテーブルを作成しました。\n\n"
            "meta:\n"
            "  logical_name: ユーザー\n"
            "  physical_name: users\n"
            "  description: ユーザー管理\n"
            "\n"
            "columns[1]{symbol,logical_name,physical_name,type,"
            "nullable,pk,unique,default,fk_target,description}:\n"
            "  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー\n"
            "\n"
            "以上です。"
        )

        # Act
        blocks = chat_service.extract_toon_blocks(text)

        # Assert
        assert len(blocks) == 1
        assert "meta:" in blocks[0]
        assert "columns[1]" in blocks[0]

    def test_TOONブロックがない応答は空リストを返す(self) -> None:
        # Arrange
        text = "テーブル設計について質問があればお聞きください。"

        # Act
        blocks = chat_service.extract_toon_blocks(text)

        # Assert
        assert blocks == []


class TestIdentifyRelevantTables:
    def test_関連テーブル名をJSON配列で返す(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        fake_response = '["users", "orders"]'
        fake = make_fake_openai_client(response=fake_response)
        monkeypatch.setattr("app.chat_service.ai_service.get_client", lambda: fake)
        index = IndexDocument(
            description="",
            rules=[],
            tables=[
                TableSummary(
                    symbol="TABLE_0001",
                    name="users",
                    logical_name="ユーザー",
                    description="",
                ),
                TableSummary(
                    symbol="TABLE_0002",
                    name="orders",
                    logical_name="注文",
                    description="",
                ),
            ],
            er_diagram="",
        )

        # Act
        result = chat_service.identify_relevant_tables("注文テーブルにFK追加", index)

        # Assert
        assert result == ["users", "orders"]

    def test_テーブル操作なしなら空リストを返す(self) -> None:
        # Arrange
        index = IndexDocument(description="", rules=[], tables=[], er_diagram="")

        # Act
        result = chat_service.identify_relevant_tables("こんにちは", index)

        # Assert
        assert result == []

    def test_JSONパース失敗時に警告ログを出力する(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        fake = make_fake_openai_client(response="not json")
        monkeypatch.setattr("app.chat_service.ai_service.get_client", lambda: fake)
        index = IndexDocument(
            description="",
            rules=[],
            tables=[
                TableSummary(symbol="TABLE_0001", name="t", logical_name="t", description=""),
            ],
            er_diagram="",
        )

        # Act
        with caplog.at_level(logging.WARNING):
            result = chat_service.identify_relevant_tables("テスト", index)

        # Assert
        assert result == []
        assert "Stage 1 JSON パース失敗" in caplog.text


class TestApplyTableActions:
    def test_新規テーブルのTOONブロックを保存する(self) -> None:
        # Arrange
        toon_blocks = [SAMPLE_CORE_TOON]
        index = IndexDocument(description="", rules=[], tables=[], er_diagram="")

        # Act
        actions = chat_service.apply_table_actions(toon_blocks, index)

        # Assert
        assert len(actions) == 1
        assert actions[0].type == "create_table"
        assert actions[0].table_name == "stub_table"

    def test_新規テーブル作成時にログを出力する(self, caplog: pytest.LogCaptureFixture) -> None:
        # Arrange
        toon_blocks = [SAMPLE_CORE_TOON]
        index = IndexDocument(description="", rules=[], tables=[], er_diagram="")

        # Act
        with caplog.at_level(logging.INFO):
            chat_service.apply_table_actions(toon_blocks, index)

        # Assert
        assert "テーブル作成: table=stub_table" in caplog.text

    def test_既存テーブルのTOONブロックで更新する(self) -> None:
        # Arrange — 先に既存テーブルを作成
        from app import table_service
        from app.derive_service import derive_all
        from app.toon_io import parse_table_toon

        doc = parse_table_toon(SAMPLE_CORE_TOON)
        doc = doc.model_copy(update={"meta": doc.meta.model_copy(update={"symbol": "TABLE_0001"})})
        doc = derive_all(doc)
        table_service.save_table("stub_table", doc)
        table_service.rebuild_index()

        index = table_service.get_index()
        toon_blocks = [SAMPLE_CORE_TOON]

        # Act
        actions = chat_service.apply_table_actions(toon_blocks, index)

        # Assert
        assert len(actions) == 1
        assert actions[0].type == "update_table"
        assert actions[0].table_name == "stub_table"


class TestGenerateResponseStream:
    def test_テストモードでスタブ応答をストリーミングする(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange
        monkeypatch.setenv("SYSDEN_TEST_MODE", "1")
        conv = chat_service.reset_conversation()
        chat_service.add_user_message(conv, "テーブルを作って")

        # Act
        chunks: list[str] = []

        async def collect() -> None:
            async for chunk in chat_service.generate_response_stream(conv):
                chunks.append(chunk)

        asyncio.run(collect())

        # Assert
        full = "".join(chunks)
        assert "meta:" in full
        assert "columns[" in full
