"""ページ間遷移・エンドツーエンドフローの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect

_TABLE_NAME = "stub_table"
_TABLE_DISPLAY = "スタブ"


class TestEndToEndFlow:
    """ユーザーの典型的な操作フロー。"""

    def test_閲覧と削除のフロー(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在しない状態でトップページを表示する
        page.goto(base_url)
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

        # When: API 経由でテーブルを作成してページをリロードする
        create_table()
        page.reload()

        # Then: 作成したテーブルの行が表示される
        expect(page.locator("#table-list tbody tr").first).to_be_visible()

        # When: テーブル名リンクで詳細ページに遷移する
        page.click(f'#table-list a[href="/tables/{_TABLE_NAME}"]')
        page.wait_for_url(f"**/{_TABLE_NAME}")
        expect(page.locator("h1")).to_be_visible()

        # When: 戻るアイコンで一覧に戻る
        page.click('a[href="/"][aria-label="一覧に戻る"]')
        page.wait_for_url(f"{base_url}/")

        # Then: テーブルの行が表示される
        expect(page.locator("#table-list tbody tr").first).to_be_visible()
        table_row = page.locator("#table-list tbody tr").first

        # When: 削除ボタン → ダイアログで受け入れる
        table_name = table_row.locator("a").first.inner_text()
        page.on("dialog", lambda d: d.accept())
        table_row.locator("button", has_text="削除").click()

        # Then: 行が消える
        expect(page.locator("#table-list tbody tr", has_text=table_name)).not_to_be_visible()

        # When: ページを再読み込みする
        page.reload()

        # Then: 空メッセージが表示される
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

    def test_一覧から詳細へのリンク遷移(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブルが存在する
        create_table()

        # When: トップページでテーブル名リンクをクリックする
        page.goto(base_url)
        page.click(f'#table-list a[href="/tables/{_TABLE_NAME}"]')

        # Then: 詳細ページに遷移する
        page.wait_for_url(f"**/{_TABLE_NAME}")
        expect(page.locator("h1")).to_have_text(_TABLE_DISPLAY)
        expect(page.locator(".tabs")).to_be_visible()
