"""GET /tables/{name} — テーブル詳細ページの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect


class TestTableDetailDisplay:
    """テーブル詳細ページの表示要素。"""

    def test_shows_table_name_heading(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: h1 にテーブル名が表示される
        expect(page.locator("h1")).to_have_text("users")

    def test_shows_page_title(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: ページタイトルが正しい
        expect(page).to_have_title("users — sysden")

    def test_shows_back_icon(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: 一覧に戻るアイコンリンクが / を指す
        back_link = page.locator('a[href="/"][aria-label="一覧に戻る"]')
        expect(back_link).to_be_visible()

    def test_shows_rendered_table(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: #table-view 内に HTML テーブルが描画される
        table_view = page.locator("#table-view")
        expect(table_view).to_be_visible()
        expect(table_view.locator("table")).to_be_visible()

        # Then: ヘッダーに日本語カラム名が含まれる
        expect(table_view.locator("th", has_text="カラム名")).to_be_visible()

        # Then: データ行に "id" が含まれる（PK は太字で表示）
        expect(table_view.locator("td >> strong", has_text="id")).to_be_visible()

    def test_shows_update_form(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: 更新フォームが正しい action を持つ
        form = page.locator('form[action="/api/tables/users"]')
        expect(form).to_be_visible()
        expect(form).to_have_attribute("method", "post")

        # Then: 依頼文テキストエリアが存在する
        expect(form.locator('textarea[name="prompt"]')).to_be_visible()

        # Then: 更新ボタンが存在する
        expect(form.locator('button[type="submit"]')).to_have_text("更新を依頼")

    def test_shows_update_heading(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: "AI に更新を依頼" 見出しが表示される
        expect(page.locator("h2", has_text="AI に更新を依頼")).to_be_visible()

    def test_nav_link_exists(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/users")

        # Then: ナビバーの sysden リンクが / を指す
        expect(page.locator('nav a[href="/"]')).to_be_visible()

    def test_shows_markdown_description(
        self, page: Page, base_url: str, create_table_auto: Callable[..., None]
    ) -> None:
        # Given: テーブルがテストモードで作成される（AI が名前 + TSV + markdown を生成）
        create_table_auto()

        # When: 詳細ページにアクセスする
        page.goto(f"{base_url}/tables/stub_table")

        # Then: markdown の内容がレンダリングされている
        expect(page.locator("#table-view")).to_contain_text("テスト用テーブル")

        # Then: 埋め込み TSV テーブルも表示される
        expect(page.locator("#table-view table")).to_be_visible()


class TestTableDetailUpdate:
    """テーブル更新フォームの操作。"""

    def test_update_redirects_to_same_page(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在し詳細ページを表示中
        create_table("users")
        page.goto(f"{base_url}/tables/users")

        # When: 更新フォームに入力して送信する
        page.fill('textarea[name="prompt"]', "email カラムを追加して")
        page.click('button[type="submit"]')

        # Then: 同じ詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/users")
        expect(page.locator("h1")).to_have_text("users")

        # Then: テーブルが表示される
        expect(page.locator("#table-view table")).to_be_visible()


class TestTableDetailNavigation:
    """テーブル詳細ページからのナビゲーション。"""

    def test_back_icon_goes_to_index(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル詳細ページを表示中
        create_table("users")
        page.goto(f"{base_url}/tables/users")

        # When: 戻るアイコンをクリックする
        page.click('a[href="/"][aria-label="一覧に戻る"]')

        # Then: トップページに遷移する
        page.wait_for_url(f"{base_url}/")
        expect(page.locator("h1")).to_have_text("テーブル一覧")

    def test_nav_logo_goes_to_index(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル詳細ページを表示中
        create_table("users")
        page.goto(f"{base_url}/tables/users")

        # When: ナビバーの "sysden" リンクをクリックする
        page.click("nav a")

        # Then: トップページに遷移する
        page.wait_for_url(f"{base_url}/")
        expect(page.locator("h1")).to_have_text("テーブル一覧")


class TestTableDetailError:
    """テーブル詳細ページのエラーケース。"""

    def test_nonexistent_table_returns_error(self, page: Page, base_url: str) -> None:
        # Given: テーブル "nonexistent" が存在しない

        # When: 存在しないテーブルの詳細ページにアクセスする
        resp = page.goto(f"{base_url}/tables/nonexistent")

        # Then: 404 エラーが返る
        assert resp is not None
        assert resp.status == 404
