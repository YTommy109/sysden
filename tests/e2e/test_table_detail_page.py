"""GET /tables/{name} — テーブル詳細ページの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect

_TABLE_NAME = "stub_table"
_TABLE_DISPLAY = "スタブ"


class TestTableDetailDisplay:
    """テーブル詳細ページの表示要素。"""

    def test_テーブル名の見出しが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する（テストモードでは "スタブ" が作成される）
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: h1 に論理名が表示される
        expect(page.locator("h1")).to_have_text(_TABLE_DISPLAY)

    def test_ページタイトルが正しい(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: ページタイトルが正しい
        expect(page).to_have_title(f"{_TABLE_DISPLAY} — sysden")

    def test_戻るアイコンが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: 一覧に戻るアイコンリンクが / を指す
        back_link = page.locator('a[href="/"][aria-label="一覧に戻る"]')
        expect(back_link).to_be_visible()

    def test_論理設計タブが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: 論理設計タブが存在し初期状態でアクティブ
        tab = page.locator(".tabs button", has_text="論理設計")
        expect(tab).to_be_visible()
        expect(tab).to_have_class("tab active")

    def test_物理設計タブが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: 物理設計タブが存在する
        tab = page.locator(".tabs button", has_text="物理設計")
        expect(tab).to_be_visible()

    def test_DAOタブが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: DAO タブが存在する
        tab = page.locator(".tabs button", has_text="DAO")
        expect(tab).to_be_visible()

    def test_論理設計が初期表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: 論理設計コンテンツが表示されている
        expect(page.locator("#logical")).to_be_visible()

    def test_物理設計は初期状態で非表示(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: 物理設計コンテンツは非表示
        expect(page.locator("#physical")).to_be_hidden()

    def test_ナビバーリンクが存在する(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # Then: ナビバーの sysden リンクが / を指す
        expect(page.locator('nav a[href="/"]')).to_be_visible()


class TestTabSwitching:
    """タブ切り替え UI のテスト。"""

    def test_物理設計タブクリックで物理設計が表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在し詳細ページを表示中
        create_table()
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # When: 物理設計タブをクリックする
        page.locator(".tabs button", has_text="物理設計").click()

        # Then: 物理設計が表示され論理設計が非表示になる
        expect(page.locator("#physical")).to_be_visible()
        expect(page.locator("#logical")).to_be_hidden()

    def test_DAOタブクリックでDAOが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在し詳細ページを表示中
        create_table()
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # When: DAO タブをクリックする
        page.locator(".tabs button", has_text="DAO").click()

        # Then: DAO が表示され他が非表示になる
        expect(page.locator("#dao")).to_be_visible()
        expect(page.locator("#logical")).to_be_hidden()
        expect(page.locator("#physical")).to_be_hidden()

    def test_論理設計タブに戻れる(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: 物理設計タブが選択された状態
        create_table()
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")
        page.locator(".tabs button", has_text="物理設計").click()
        expect(page.locator("#physical")).to_be_visible()

        # When: 論理設計タブをクリックする
        page.locator(".tabs button", has_text="論理設計").click()

        # Then: 論理設計が再表示され物理設計が非表示になる
        expect(page.locator("#logical")).to_be_visible()
        expect(page.locator("#physical")).to_be_hidden()


class TestTableDetailNavigation:
    """テーブル詳細ページからのナビゲーション。"""

    def test_戻るアイコンで一覧に遷移する(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル詳細ページを表示中
        create_table()
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # When: 戻るアイコンをクリックする
        page.click('a[href="/"][aria-label="一覧に戻る"]')

        # Then: トップページに遷移する
        page.wait_for_url(f"{base_url}/")
        expect(page.locator("h1")).to_have_text("テーブル一覧")

    def test_ナビロゴで一覧に遷移する(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル詳細ページを表示中
        create_table()
        page.goto(f"{base_url}/tables/{_TABLE_NAME}")

        # When: ナビバーの "sysden" リンクをクリックする
        page.click("nav a")

        # Then: トップページに遷移する
        page.wait_for_url(f"{base_url}/")
        expect(page.locator("h1")).to_have_text("テーブル一覧")


class TestTableDetailError:
    """テーブル詳細ページのエラーケース。"""

    def test_存在しないテーブルで404(self, page: Page, base_url: str) -> None:
        # Given: テーブル "nonexistent" が存在しない

        # When: 存在しないテーブルの詳細ページにアクセスする
        resp = page.goto(f"{base_url}/tables/nonexistent")

        # Then: 404 エラーが返る
        assert resp is not None
        assert resp.status == 404
