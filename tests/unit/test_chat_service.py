import logging

import pytest

from app import chat_service
from app.models import ChatAction


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
