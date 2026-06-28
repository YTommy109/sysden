"""チャットパネルの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect


class TestChatToggle:
    def test_チャットパネルの開閉(self, page: Page, base_url: str) -> None:
        # Given: トップページを表示
        page.goto(base_url)

        # When: チャットトグルボタンをクリック
        page.click("#chat-toggle-btn")

        # Then: チャットパネルが表示される
        expect(page.locator("#chat-panel")).to_be_visible()

        # When: もう一度クリック
        page.click("#chat-toggle-btn")

        # Then: チャットパネルが非表示になる
        expect(page.locator("#chat-panel")).to_be_hidden()

    def test_チャットの開閉状態がページ遷移後も維持される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: チャットを開いた状態でトップページを表示
        page.goto(base_url)
        page.click("#chat-toggle-btn")
        expect(page.locator("#chat-panel")).to_be_visible()

        # When: テーブル詳細ページに遷移する
        create_table()
        page.goto(base_url)
        page.click("a:has-text('スタブ')")

        # Then: チャットパネルが開いたままである
        expect(page.locator("#chat-panel")).to_be_visible()


class TestChatMessaging:
    def test_メッセージを送信してストリーミング応答を受信する(
        self, page: Page, base_url: str
    ) -> None:
        # Given: チャットを開いた状態
        page.goto(base_url)
        page.click("#chat-toggle-btn")

        # When: メッセージを送信する
        page.fill("#chat-input", "テーブルを作って")
        page.click("#chat-send-btn")

        # Then: ユーザーメッセージが表示される
        expect(page.locator(".chat-msg.user")).to_have_count(1)

        # Then: アシスタントの応答が表示される（ストリーミング完了を待つ）
        expect(page.locator(".chat-msg.assistant")).to_have_count(1, timeout=10000)

    def test_Ctrl_Enterで送信できる(self, page: Page, base_url: str) -> None:
        # Given: チャットを開いた状態
        page.goto(base_url)
        page.click("#chat-toggle-btn")

        # When: Ctrl+Enter で送信する
        page.fill("#chat-input", "こんにちは")
        page.press("#chat-input", "Control+Enter")

        # Then: メッセージが送信される
        expect(page.locator(".chat-msg.user")).to_have_count(1)


class TestChatContentUpdate:
    def test_テーブル作成後に一覧が自動更新される(self, page: Page, base_url: str) -> None:
        # Given: テーブルがない状態でチャットを開く
        page.goto(base_url)
        page.click("#chat-toggle-btn")
        expect(page.locator("#main-content")).to_contain_text("テーブル設計はまだありません")

        # When: チャットでテーブル作成を依頼する
        page.fill("#chat-input", "テーブルを作って")
        page.click("#chat-send-btn")

        # Then: 左側の一覧にテーブルが表示される（content_updated による自動更新）
        expect(page.locator("#main-content a:has-text('スタブ')")).to_be_visible(timeout=15000)


class TestChatReset:
    def test_リセットで会話がクリアされる(self, page: Page, base_url: str) -> None:
        # Given: メッセージを送信した状態
        page.goto(base_url)
        page.click("#chat-toggle-btn")
        page.fill("#chat-input", "こんにちは")
        page.click("#chat-send-btn")
        expect(page.locator(".chat-msg.user")).to_have_count(1, timeout=5000)

        # When: リセットボタンをクリック
        page.click("#chat-reset-btn")

        # Then: メッセージがクリアされる
        expect(page.locator(".chat-msg")).to_have_count(0, timeout=5000)
