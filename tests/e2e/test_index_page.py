"""GET / — テーブル一覧ページの E2E テスト。"""

from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Dialog, Page, expect


def _capture_and_dismiss(messages: list[str]) -> Callable[[Dialog], None]:
    def _handler(d: Dialog) -> None:
        messages.append(d.message)
        d.dismiss()

    return _handler


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

    def test_shows_add_button(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "テーブル追加" ボタンが表示される
        expect(page.locator('button:has-text("テーブル追加")')).to_be_visible()

    def test_dialog_closed_by_default(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: ダイアログは初期状態で閉じている
        dialog = page.locator("#create-dialog")
        expect(dialog).not_to_be_visible()

    def test_dialog_opens_on_button_click(self, page: Page, base_url: str) -> None:
        # Given: トップページにアクセスする
        page.goto(base_url)

        # When: "テーブル追加" ボタンをクリックする
        page.locator('button:has-text("テーブル追加")').click()

        # Then: ダイアログが開く
        dialog = page.locator("#create-dialog")
        expect(dialog).to_be_visible()

    def test_dialog_has_form_fields(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # Then: 依頼文テキストエリアが存在する
        prompt_textarea = page.locator('#create-dialog textarea[name="prompt"]')
        expect(prompt_textarea).to_be_visible()
        expect(prompt_textarea).to_have_attribute("required", "")

        # Then: 送信ボタンが存在する
        submit_btn = page.locator('#create-dialog button[type="submit"]')
        expect(submit_btn).to_be_visible()
        expect(submit_btn).to_have_text("依頼を送信")

    def test_dialog_form_action_points_to_api(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # Then: フォームの action が /api/tables を指す
        form = page.locator('#create-dialog form[action="/api/tables"]')
        expect(form).to_be_visible()
        expect(form).to_have_attribute("method", "post")

    def test_dialog_cancel_closes(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        expect(page.locator("#create-dialog")).to_be_visible()

        # When: キャンセルボタンをクリックする
        page.locator('#create-dialog button:has-text("キャンセル")').click()

        # Then: ダイアログが閉じる
        expect(page.locator("#create-dialog")).not_to_be_visible()

    def test_no_er_diagram_when_empty(self, page: Page, base_url: str) -> None:
        # Given: テーブルが存在しない

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図セクションが表示されない
        expect(page.locator("#er-diagram")).not_to_be_visible()

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
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "users" を含むカードが表示される
        card = page.locator(".card", has_text="users")
        expect(card).to_be_visible()

    def test_card_has_view_link(
        self, page: Page, base_url: str, create_table: Callable[..., None]
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
        self, page: Page, base_url: str, create_table: Callable[..., None]
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
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示されない
        expect(page.locator("text=テーブル設計はまだありません。")).not_to_be_visible()

    def test_multiple_tables_shown(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" と "orders" が存在する
        create_table("users")
        create_table("orders")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 両方のカードが表示される
        expect(page.locator(".card", has_text="users")).to_be_visible()
        expect(page.locator(".card", has_text="orders")).to_be_visible()

    def test_er_diagram_shown(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図セクションが表示される
        expect(page.locator("#er-diagram")).to_be_visible()

    def test_er_diagram_contains_table_names(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" と "orders" が存在する
        create_table("users")
        create_table("orders")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図に両テーブル名が含まれる
        er_section = page.locator("#er-diagram")
        expect(er_section).to_contain_text("users")
        expect(er_section).to_contain_text("orders")


class TestCreateTableDialog:
    """テーブル新規作成ダイアログの操作。"""

    def test_create_redirects_to_detail(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # When: 依頼文を入力して送信する
        page.fill('#create-dialog textarea[name="prompt"]', "ユーザーテーブルを作って")
        page.click('#create-dialog button[type="submit"]')

        # Then: テーブル詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/*")
        expect(page.locator("h1")).to_be_visible()

    def test_prompt_required_validation(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # When: prompt を空のまま送信ボタンを押す
        page.click('#create-dialog button[type="submit"]')

        # Then: ページ遷移しない（HTML required バリデーション）
        expect(page).to_have_url(base_url + "/")

    def test_submit_via_meta_enter(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いて依頼文を入力した状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        textarea = page.locator('#create-dialog textarea[name="prompt"]')
        textarea.fill("ユーザーテーブルを作って")

        # When: Cmd+Enter（Meta+Enter）を押す
        textarea.press("Meta+Enter")

        # Then: テーブル詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/*")
        expect(page.locator("h1")).to_be_visible()

    def test_submit_via_ctrl_enter(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いて依頼文を入力した状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        textarea = page.locator('#create-dialog textarea[name="prompt"]')
        textarea.fill("ユーザーテーブルを作って")

        # When: Ctrl+Enter を押す
        textarea.press("Control+Enter")

        # Then: テーブル詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/*")
        expect(page.locator("h1")).to_be_visible()

    def test_created_table_appears_on_index(self, page: Page, base_url: str) -> None:
        # Given: ダイアログからテーブルを作成する
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        page.fill('#create-dialog textarea[name="prompt"]', "商品テーブル")
        page.click('#create-dialog button[type="submit"]')
        page.wait_for_url("**/tables/*")

        # When: トップページに戻る
        page.goto(base_url)

        # Then: 作成したテーブルのカードが表示される
        expect(page.locator(".card")).to_be_visible()


class TestRebuildButtons:
    """テーブル一覧・ER 図の再作成ボタン。"""

    def test_rebuild_index_tables_button_visible(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "テーブル一覧の再作成" ボタンが表示される
        btn = page.locator('button:has-text("テーブル一覧の再作成")')
        expect(btn).to_be_visible()

    def test_rebuild_er_diagram_button_visible(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "ER 図の再作成" ボタンが表示される
        btn = page.locator('button:has-text("ER 図の再作成")')
        expect(btn).to_be_visible()

    def test_rebuild_index_tables_restores_list(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在するが index.tsv がない
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)
        expect(page.locator("text=テーブル設計はまだありません。")).to_be_visible()

        # When: "テーブル一覧の再作成" ボタンをクリックする
        page.locator('button:has-text("テーブル一覧の再作成")').click()
        page.wait_for_url("**/")

        # Then: テーブルカードが表示される
        expect(page.locator(".card", has_text="users")).to_be_visible()

    def test_rebuild_er_diagram_restores_diagram(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在するが index.mmd がない
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)
        expect(page.locator("#er-diagram")).not_to_be_visible()

        # When: "ER 図の再作成" ボタンをクリックする
        page.locator('button:has-text("ER 図の再作成")').click()
        page.wait_for_url("**/")

        # Then: ER 図が表示される
        expect(page.locator("#er-diagram")).to_be_visible()


class TestDeleteTable:
    """テーブル削除（htmx hx-delete + hx-confirm）。"""

    def test_delete_shows_confirm_dialog(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタンをクリックする
        dialog_messages: list[str] = []
        page.on("dialog", _capture_and_dismiss(dialog_messages))
        card = page.locator(".card", has_text="users")
        card.locator("button", has_text="削除").click()

        # Then: 確認ダイアログが表示される
        page.wait_for_timeout(500)
        assert len(dialog_messages) == 1
        assert "users" in dialog_messages[0]
        assert "削除" in dialog_messages[0]

    def test_delete_cancel_keeps_card(
        self, page: Page, base_url: str, create_table: Callable[..., None]
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
        self, page: Page, base_url: str, create_table: Callable[..., None]
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
