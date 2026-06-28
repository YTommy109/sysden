import pytest
from fastapi.testclient import TestClient

from app import chat_service


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")


class TestChatHistory:
    def test_空の履歴を返す(self, client: TestClient) -> None:
        # Given: 会話がない状態

        # When: 履歴 API にアクセスする
        resp = client.get("/api/chat/history")

        # Then: 空のメッセージ配列が返る
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_既存メッセージを含む履歴を返す(self, client: TestClient) -> None:
        # Given: メッセージが追加された会話
        conv = chat_service.load_conversation()
        chat_service.add_user_message(conv, "テスト")

        # When: 履歴 API にアクセスする
        resp = client.get("/api/chat/history")

        # Then: メッセージが含まれる
        data = resp.json()
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "テスト"


class TestChatWebSocket:
    def test_メッセージを送信してストリーミング応答を受信する(
        self, client: TestClient, mock_openai: None
    ) -> None:
        # Given: WebSocket 接続
        with client.websocket_connect("/ws/chat") as ws:
            # When: メッセージを送信する
            ws.send_json({"type": "message", "content": "テーブルを作って"})

            # Then: stream → stream_end が届く
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] in ("stream_end", "error"):
                    break

            stream_msgs = [m for m in messages if m["type"] == "stream"]
            assert len(stream_msgs) > 0

            end_msg = next(m for m in messages if m["type"] == "stream_end")
            assert "meta:" in end_msg["content"]

    def test_リセットで空の履歴が返る(self, client: TestClient) -> None:
        # Given: WebSocket 接続
        with client.websocket_connect("/ws/chat") as ws:
            # When: リセットを送信する
            ws.send_json({"type": "reset"})

            # Then: 空の履歴メッセージが返る
            msg = ws.receive_json()
            assert msg["type"] == "history"
            assert msg["messages"] == []

    def test_空メッセージはエラーを返す(self, client: TestClient) -> None:
        # Given: WebSocket 接続
        with client.websocket_connect("/ws/chat") as ws:
            # When: 空メッセージを送信する
            ws.send_json({"type": "message", "content": ""})

            # Then: エラーが返る
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_テーブル作成後にcontent_updatedが届く(
        self, client: TestClient, mock_openai: None
    ) -> None:
        # Given: WebSocket 接続
        with client.websocket_connect("/ws/chat") as ws:
            # When: テーブル作成を依頼する
            ws.send_json({"type": "message", "content": "テーブルを作って"})

            # Then: stream_end の後に content_updated が届く
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "content_updated":
                    break
                if msg["type"] == "error":
                    break

            types = [m["type"] for m in messages]
            assert "stream_end" in types
            assert "content_updated" in types
