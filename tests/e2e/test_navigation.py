"""ページ間遷移・エンドツーエンドフローの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect


class TestEndToEndFlow:
    """ユーザーの典型的な操作フロー。"""

    def test_create_view_delete_flow(self, page: Page, base_url: str) -> None:
        # Given: テーブルが存在しない状態でトップページを表示する
        page.goto(base_url)
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

        # When: フォームでテーブル "users" を作成する
        page.fill('input[name="name"]', "users")
        page.fill('textarea[name="prompt"]', "ユーザーテーブル")
        page.click('button[type="submit"]')

        # Then: 詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/users")
        expect(page.locator("h1")).to_have_text("users")

        # When: 一覧に戻る
        page.click('a[href="/"]:has-text("一覧に戻る")')
        page.wait_for_url(f"{base_url}/")

        # Then: 作成したテーブルのカードが表示される
        card = page.locator(".card", has_text="users")
        expect(card).to_be_visible()

        # When: 削除ボタン → ダイアログで受け入れる
        page.on("dialog", lambda d: d.accept())
        card.locator("button", has_text="削除").click()

        # Then: カードが消える
        expect(page.locator(".card", has_text="users")).not_to_be_visible()

        # When: ページを再読み込みする
        page.reload()

        # Then: 空メッセージが表示される
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

    def test_create_then_update_flow(self, page: Page, base_url: str) -> None:
        # Given: トップページからテーブルを作成する
        page.goto(base_url)
        page.fill('input[name="name"]', "orders")
        page.fill('textarea[name="prompt"]', "注文テーブル")
        page.click('button[type="submit"]')
        page.wait_for_url("**/tables/orders")

        # When: 詳細ページで更新を依頼する
        page.fill('textarea[name="prompt"]', "ステータスカラムを追加して")
        page.click('button[type="submit"]')

        # Then: 同じ詳細ページに留まり、テーブルが表示される
        page.wait_for_url("**/tables/orders")
        expect(page.locator("h1")).to_have_text("orders")
        expect(page.locator("#table-view table")).to_be_visible()

    def test_index_link_to_detail(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページで "参照・編集" リンクをクリックする
        page.goto(base_url)
        page.click('.card a[href="/tables/users"]')

        # Then: 詳細ページに遷移する
        page.wait_for_url("**/tables/users")
        expect(page.locator("h1")).to_have_text("users")
        expect(page.locator("#table-view table")).to_be_visible()
