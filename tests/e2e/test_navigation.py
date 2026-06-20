"""ページ間遷移・エンドツーエンドフローの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect


class TestEndToEndFlow:
    """ユーザーの典型的な操作フロー。"""

    def test_create_view_delete_flow(self, page: Page, base_url: str) -> None:
        # Given: テーブルが存在しない状態でトップページを表示する
        page.goto(base_url)
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

        # When: ダイアログを開いてテーブルを作成する
        page.locator('button:has-text("テーブル追加")').click()
        page.fill('#create-dialog textarea[name="prompt"]', "ユーザーテーブル")
        page.click('#create-dialog button[type="submit"]')

        # Then: 詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/*")
        table_name = page.locator("h1").inner_text()

        # When: 一覧に戻る
        page.click('a[href="/"]:has-text("一覧に戻る")')
        page.wait_for_url(f"{base_url}/")

        # Then: 作成したテーブルの行が表示される
        row = page.locator("#table-list tbody tr", has_text=table_name)
        expect(row).to_be_visible()

        # When: 削除ボタン → ダイアログで受け入れる
        page.on("dialog", lambda d: d.accept())
        row.locator("button", has_text="削除").click()

        # Then: 行が消える
        expect(page.locator("#table-list tbody tr", has_text=table_name)).not_to_be_visible()

        # When: ページを再読み込みする
        page.reload()

        # Then: 空メッセージが表示される
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

    def test_create_then_update_flow(self, page: Page, base_url: str) -> None:
        # Given: ダイアログからテーブルを作成する
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        page.fill('#create-dialog textarea[name="prompt"]', "注文テーブル")
        page.click('#create-dialog button[type="submit"]')
        page.wait_for_url("**/tables/*")

        # When: 詳細ページで更新を依頼する
        detail_url = page.url
        page.fill('textarea[name="prompt"]', "ステータスカラムを追加して")
        page.click('button[type="submit"]')

        # Then: 同じ詳細ページに留まり、テーブルが表示される
        page.wait_for_url(detail_url)
        expect(page.locator("h1")).to_be_visible()
        expect(page.locator("#table-view table")).to_be_visible()

    def test_index_link_to_detail(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページで "詳細" リンクをクリックする
        page.goto(base_url)
        page.click('#table-list a[href="/tables/users"]')

        # Then: 詳細ページに遷移する
        page.wait_for_url("**/tables/users")
        expect(page.locator("h1")).to_have_text("users")
        expect(page.locator("#table-view table")).to_be_visible()
