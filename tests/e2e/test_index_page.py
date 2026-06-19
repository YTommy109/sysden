"""GET / — テーブル一覧ページの E2E テスト。"""

from collections.abc import Callable

from playwright.sync_api import Page, expect


class TestIndexPageEmpty:
    """テーブルが存在しない状態でのトップページ。"""

    def test_shows_empty_message(self, page: Page, base_url: str) -> None:
        # Given: テーブルが1件も存在しない

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示される
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

    def test_shows_page_title(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: タイトルに "テーブル一覧" が含まれる
        expect(page).to_have_title("テーブル一覧 — sysden")

    def test_shows_heading(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: 見出し "テーブル設計一覧" が表示される
        expect(page.locator("h1")).to_have_text("テーブル設計一覧")

    def test_shows_create_form(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: テーブル名入力欄が存在する
        name_input = page.locator('input[name="name"]')
        expect(name_input).to_be_visible()
        expect(name_input).to_have_attribute("placeholder", "テーブル名（例: users）")
        expect(name_input).to_have_attribute("required", "")

        # Then: 依頼文テキストエリアが存在する
        prompt_textarea = page.locator('textarea[name="prompt"]')
        expect(prompt_textarea).to_be_visible()

        # Then: 送信ボタンが存在する
        submit_btn = page.locator('button[type="submit"]')
        expect(submit_btn).to_be_visible()
        expect(submit_btn).to_have_text("依頼を送信")

    def test_form_action_points_to_api(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: フォームの action が /api/tables を指す
        form = page.locator('form[action="/api/tables"]')
        expect(form).to_be_visible()
        expect(form).to_have_attribute("method", "post")

    def test_nav_link_to_home(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: ナビバーに "sysden" リンクがあり / を指す
        nav_link = page.locator('nav a[href="/"]')
        expect(nav_link).to_be_visible()
        expect(nav_link).to_have_text("sysden")


class TestIndexPageWithTables:
    """テーブルが存在する状態でのトップページ。"""

    def test_shows_table_card(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "users" を含むカードが表示される
        card = page.locator(".card", has_text="users")
        expect(card).to_be_visible()

    def test_card_has_view_link(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "参照・編集" リンクが /tables/users を指す
        link = page.locator('.card a[href="/tables/users"]')
        expect(link).to_be_visible()
        expect(link).to_have_text("参照・編集")

    def test_card_has_delete_button(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "削除" ボタンが存在する
        card = page.locator(".card", has_text="users")
        delete_btn = card.locator("button", has_text="削除")
        expect(delete_btn).to_be_visible()

    def test_empty_message_not_shown(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示されない
        expect(page.locator("text=テーブル設計はまだありません。")).not_to_be_visible()

    def test_multiple_tables_shown(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" と "orders" が存在する
        create_table("users")
        create_table("orders")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 両方のカードが表示される
        expect(page.locator(".card", has_text="users")).to_be_visible()
        expect(page.locator(".card", has_text="orders")).to_be_visible()


class TestCreateTableForm:
    """テーブル新規作成フォームの操作。"""

    def test_create_redirects_to_detail(self, page: Page, base_url: str) -> None:
        # Given: トップページを表示している
        page.goto(base_url)

        # When: フォームに入力して送信する
        page.fill('input[name="name"]', "users")
        page.fill('textarea[name="prompt"]', "ユーザーテーブルを作って")
        page.click('button[type="submit"]')

        # Then: テーブル詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/users")
        expect(page.locator("h1")).to_have_text("users")

    def test_name_required_validation(self, page: Page, base_url: str) -> None:
        # Given: トップページを表示している
        page.goto(base_url)

        # When: name を空のまま送信ボタンを押す
        page.click('button[type="submit"]')

        # Then: ページ遷移しない（HTML required バリデーション）
        expect(page).to_have_url(base_url + "/")

    def test_created_table_appears_on_index(self, page: Page, base_url: str) -> None:
        # Given: フォームでテーブルを作成する
        page.goto(base_url)
        page.fill('input[name="name"]', "products")
        page.fill('textarea[name="prompt"]', "商品テーブル")
        page.click('button[type="submit"]')
        page.wait_for_url("**/tables/products")

        # When: トップページに戻る
        page.goto(base_url)

        # Then: 作成したテーブルのカードが表示される
        expect(page.locator(".card", has_text="products")).to_be_visible()


class TestDeleteTable:
    """テーブル削除（htmx hx-delete + hx-confirm）。"""

    def test_delete_shows_confirm_dialog(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタンをクリックする
        dialog_messages: list[str] = []
        page.on("dialog", lambda d: (dialog_messages.append(d.message), d.dismiss()))
        card = page.locator(".card", has_text="users")
        card.locator("button", has_text="削除").click()

        # Then: 確認ダイアログが表示される
        page.wait_for_timeout(500)
        assert len(dialog_messages) == 1
        assert "users" in dialog_messages[0]
        assert "削除" in dialog_messages[0]

    def test_delete_cancel_keeps_card(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタン → ダイアログでキャンセルする
        page.on("dialog", lambda d: d.dismiss())
        card = page.locator(".card", has_text="users")
        card.locator("button", has_text="削除").click()

        # Then: カードが残っている
        page.wait_for_timeout(500)
        expect(page.locator(".card", has_text="users")).to_be_visible()

    def test_delete_accept_removes_card(
        self, page: Page, base_url: str, create_table: Callable[[str, str], None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタン → ダイアログで受け入れる
        page.on("dialog", lambda d: d.accept())
        card = page.locator(".card", has_text="users")
        card.locator("button", has_text="削除").click()

        # Then: "users" カードが DOM から消える
        expect(page.locator(".card", has_text="users")).not_to_be_visible()
