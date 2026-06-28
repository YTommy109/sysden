"""GET / — テーブル一覧ページの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Dialog, Page, expect


def _capture_and_dismiss(messages: list[str]) -> Callable[[Dialog], None]:
    def _handler(d: Dialog) -> None:
        messages.append(d.message)
        d.dismiss()

    return _handler


class TestIndexPageEmpty:
    """テーブルが存在しない状態でのトップページ。"""

    def test_空メッセージが表示される(self, page: Page, base_url: str) -> None:
        # Given: テーブルが1件も存在しない

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示される
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

    def test_ページタイトルが正しい(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: タイトルに "テーブル一覧" が含まれる
        expect(page).to_have_title("テーブル一覧 — sysden")

    def test_見出しが表示される(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: 見出し "テーブル一覧" が表示される
        expect(page.locator("h1")).to_have_text("テーブル一覧")

    def test_チャットトグルボタンが表示される(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: チャットトグルボタンが表示される
        expect(page.locator("#chat-toggle-btn")).to_be_visible()

    def test_テーブルなしでER図は非表示(self, page: Page, base_url: str) -> None:
        # Given: テーブルが存在しない

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図の mermaid コンテンツが表示されない
        expect(page.locator("#er-diagram .mermaid")).not_to_be_visible()

    def test_ナビバーにホームリンクがある(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: ナビバーに "sysden" リンクがあり / を指す
        nav_link = page.locator('nav a[href="/"]')
        expect(nav_link).to_be_visible()
        expect(nav_link).to_have_text("sysden")


class TestIndexPageWithTables:
    """テーブルが存在する状態でのトップページ。"""

    def test_テーブル行が表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する（テストモードでは stub_table / スタブ が作成される）
        create_table()

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: テーブル行が少なくとも1行表示される
        expect(page.locator("#table-list tbody tr").first).to_be_visible()

    def test_テーブル名が詳細ページへのリンク(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する（テストモードでは stub_table が作成される）
        create_table()

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: テーブル名が詳細ページへのリンクになっている
        link = page.locator('#table-list a[href="/tables/stub_table"]')
        expect(link).to_be_visible()

    def test_行に削除ボタンがある(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "削除" ボタンが存在する
        delete_btn = page.locator("#table-list tbody tr").first.locator("button", has_text="削除")
        expect(delete_btn).to_be_visible()

    def test_空メッセージが非表示(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示されない
        expect(page.locator("text=テーブル設計はまだありません。")).not_to_be_visible()

    def test_ER図セクションが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図セクションが表示される
        expect(page.locator("#er-diagram")).to_be_visible()


class TestRebuildButtons:
    """テーブル一覧・ER 図の再作成ボタン。"""

    def test_テーブル一覧再作成ボタンが表示される(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "テーブル一覧の再作成" ボタンが表示される
        btn = page.locator('button[aria-label="テーブル一覧の再作成"]')
        expect(btn).to_be_visible()

    def test_ER図再作成ボタンが表示される(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "ER 図の再作成" ボタンが表示される
        btn = page.locator('button[aria-label="ER 図の再作成"]')
        expect(btn).to_be_visible()


class TestDeleteTable:
    """テーブル削除（htmx hx-delete + hx-confirm）。"""

    def test_削除で確認ダイアログが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在しトップページを表示中
        create_table()
        page.goto(base_url)

        # When: 削除ボタンをクリックする
        dialog_messages: list[str] = []
        page.on("dialog", _capture_and_dismiss(dialog_messages))
        row = page.locator("#table-list tbody tr").first
        row.locator("button", has_text="削除").click()

        # Then: 確認ダイアログが表示される
        page.wait_for_timeout(500)
        assert len(dialog_messages) == 1
        assert "削除" in dialog_messages[0]

    def test_削除キャンセルで行が残る(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在しトップページを表示中
        create_table()
        page.goto(base_url)

        # When: 削除ボタン → ダイアログでキャンセルする
        page.on("dialog", lambda d: d.dismiss())
        row = page.locator("#table-list tbody tr").first
        row.locator("button", has_text="削除").click()

        # Then: 行が残っている
        page.wait_for_timeout(500)
        expect(page.locator("#table-list tbody tr").first).to_be_visible()

    def test_削除承認で行が消える(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在しトップページを表示中
        create_table()
        page.goto(base_url)

        # When: 削除ボタン → ダイアログで受け入れる
        page.on("dialog", lambda d: d.accept())
        row = page.locator("#table-list tbody tr").first
        table_name = row.locator("a").first.inner_text()
        row.locator("button", has_text="削除").click()

        # Then: 行が DOM から消える
        expect(page.locator("#table-list tbody tr", has_text=table_name)).not_to_be_visible()
