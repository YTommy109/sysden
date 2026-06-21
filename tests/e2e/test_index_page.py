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

    def test_テーブル追加ボタンが表示される(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: "テーブル追加" ボタンが表示される
        expect(page.locator('button:has-text("テーブル追加")')).to_be_visible()

    def test_ダイアログは初期状態で閉じている(self, page: Page, base_url: str) -> None:
        # Given/When: トップページにアクセスする
        page.goto(base_url)

        # Then: ダイアログは初期状態で閉じている
        dialog = page.locator("#create-dialog")
        expect(dialog).not_to_be_visible()

    def test_ボタンクリックでダイアログが開く(self, page: Page, base_url: str) -> None:
        # Given: トップページにアクセスする
        page.goto(base_url)

        # When: "テーブル追加" ボタンをクリックする
        page.locator('button:has-text("テーブル追加")').click()

        # Then: ダイアログが開く
        dialog = page.locator("#create-dialog")
        expect(dialog).to_be_visible()

    def test_ダイアログにフォーム要素がある(self, page: Page, base_url: str) -> None:
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

    def test_フォームのactionがAPIを指す(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # Then: フォームの action が /api/tables を指す
        form = page.locator('#create-dialog form[action="/api/tables"]')
        expect(form).to_be_visible()
        expect(form).to_have_attribute("method", "post")

    def test_キャンセルでダイアログが閉じる(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        expect(page.locator("#create-dialog")).to_be_visible()

        # When: キャンセルボタンをクリックする
        page.locator('#create-dialog button:has-text("キャンセル")').click()

        # Then: ダイアログが閉じる
        expect(page.locator("#create-dialog")).not_to_be_visible()

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
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "users" を含む行が表示される
        row = page.locator("#table-list tbody tr", has_text="users")
        expect(row).to_be_visible()

    def test_テーブル名が詳細ページへのリンク(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: テーブル名が /tables/users へのリンクになっている
        link = page.locator('#table-list a[href="/tables/users"]')
        expect(link).to_be_visible()
        expect(link).to_have_text("users")

    def test_行に削除ボタンがある(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: "削除" ボタンが存在する
        row = page.locator("#table-list tbody tr", has_text="users")
        delete_btn = row.locator("button", has_text="削除")
        expect(delete_btn).to_be_visible()

    def test_空メッセージが非表示(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 空メッセージが表示されない
        expect(page.locator("text=テーブル設計はまだありません。")).not_to_be_visible()

    def test_複数テーブルが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" と "orders" が存在する
        create_table("users")
        create_table("orders")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: 両方の行が表示される
        expect(page.locator("#table-list tbody tr", has_text="users")).to_be_visible()
        expect(page.locator("#table-list tbody tr", has_text="orders")).to_be_visible()

    def test_ER図セクションが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在する
        create_table("users")

        # When: トップページにアクセスする
        page.goto(base_url)

        # Then: ER 図セクションが表示される
        expect(page.locator("#er-diagram")).to_be_visible()

    def test_ER図にテーブル名が含まれる(
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

    def test_作成後に詳細ページへリダイレクト(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # When: 依頼文を入力して送信する
        page.fill('#create-dialog textarea[name="prompt"]', "ユーザーテーブルを作って")
        page.click('#create-dialog button[type="submit"]')

        # Then: テーブル詳細ページにリダイレクトされる
        page.wait_for_url("**/tables/*")
        expect(page.locator("h1")).to_be_visible()

    def test_依頼文が空なら送信されない(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いた状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()

        # When: prompt を空のまま送信ボタンを押す
        page.click('#create-dialog button[type="submit"]')

        # Then: ページ遷移しない（HTML required バリデーション）
        expect(page).to_have_url(base_url + "/")

    def test_MetaEnterで送信できる(self, page: Page, base_url: str) -> None:
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

    def test_CtrlEnterで送信できる(self, page: Page, base_url: str) -> None:
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

    def test_作成したテーブルが一覧に表示される(self, page: Page, base_url: str) -> None:
        # Given: ダイアログからテーブルを作成する
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        page.fill('#create-dialog textarea[name="prompt"]', "商品テーブル")
        page.click('#create-dialog button[type="submit"]')
        page.wait_for_url("**/tables/*")

        # When: トップページに戻る
        page.goto(base_url)

        # Then: 作成したテーブルの行が表示される
        expect(page.locator("#table-list tbody tr")).to_be_visible()


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

    def test_テーブル一覧再作成でリストが復元される(
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

        # When: "テーブル一覧の再作成" ボタンをクリックする（SSE で非同期更新）
        page.locator('button[aria-label="テーブル一覧の再作成"]').click()

        # Then: テーブル行が表示される
        expect(page.locator("#table-list tbody tr", has_text="users")).to_be_visible(timeout=10000)

    def test_テーブル一覧再作成でER図も復元される(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在するが index.tsv も index.mmd もない
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)
        expect(page.locator("#er-diagram .mermaid")).not_to_be_visible()

        # When: "テーブル一覧の再作成" ボタンをクリックする（SSE で非同期更新）
        page.locator('button[aria-label="テーブル一覧の再作成"]').click()

        # Then: ER 図も再作成されて表示される
        expect(page.locator("#er-diagram .mermaid")).to_be_visible(timeout=10000)

    def test_ER図再作成でER図が復元される(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在するが index.mmd がない
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)
        expect(page.locator("#er-diagram .mermaid")).not_to_be_visible()

        # When: "ER 図の再作成" ボタンをクリックする（SSE で非同期更新）
        page.locator('button[aria-label="ER 図の再作成"]').click()

        # Then: ER 図が表示される
        expect(page.locator("#er-diagram .mermaid")).to_be_visible(timeout=10000)


class TestButtonEffects:
    """ボタンの非活性化と回転アニメーション。"""

    def test_作成送信ボタンがリクエスト中にdisabledになる(self, page: Page, base_url: str) -> None:
        # Given: ダイアログを開いて依頼文を入力した状態
        page.goto(base_url)
        page.locator('button:has-text("テーブル追加")').click()
        page.fill('#create-dialog textarea[name="prompt"]', "ユーザーテーブル")

        # When: 送信ボタンをクリックする
        submit_btn = page.locator('#create-dialog button[type="submit"]')
        submit_btn.click()

        # Then: ボタンが disabled になる（二重送信防止）
        expect(submit_btn).to_be_disabled()

        # Cleanup: ページ遷移を待つ
        page.wait_for_url("**/tables/*")

    def test_テーブル一覧再作成ボタンが回転しdisabledになる(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在する
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)

        # When: "テーブル一覧の再作成" ボタンをクリックする
        btn = page.locator('button[aria-label="テーブル一覧の再作成"]')
        btn.click()

        # Then: disabled + spinning な SSE フラグメントに置き換わる
        spinning_img = page.locator("[sse-connect] img.spinning")
        expect(spinning_img).to_be_visible()
        disabled_btn = page.locator("[sse-connect] button[disabled]")
        expect(disabled_btn).to_be_visible()

        # Then: SSE 完了後にテーブル一覧が復元される
        expect(page.locator("#table-list tbody tr", has_text="users")).to_be_visible(timeout=10000)

    def test_ER図再作成ボタンが回転しdisabledになる(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在する
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)

        # When: "ER 図の再作成" ボタンをクリックする
        btn = page.locator('button[aria-label="ER 図の再作成"]')
        btn.click()

        # Then: disabled + spinning な SSE フラグメントに置き換わる
        spinning_img = page.locator("[sse-connect] img.spinning")
        expect(spinning_img).to_be_visible()
        disabled_btn = page.locator("[sse-connect] button[disabled]")
        expect(disabled_btn).to_be_visible()

        # Then: SSE 完了後に ER 図が復元される
        expect(page.locator("#er-diagram .mermaid")).to_be_visible(timeout=10000)

    def test_テーブル一覧再作成ボタンが完了後に復元される(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在する
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)

        # When: "テーブル一覧の再作成" ボタンをクリックして完了を待つ
        page.locator('button[aria-label="テーブル一覧の再作成"]').click()
        expect(page.locator("#table-list tbody tr", has_text="users")).to_be_visible(timeout=10000)

        # Then: 再作成ボタンが元の状態（有効・回転なし）に戻る
        btn = page.locator('button[aria-label="テーブル一覧の再作成"]')
        expect(btn).to_be_enabled()
        expect(btn.locator("img.spinning")).not_to_be_visible()

    def test_ER図再作成ボタンが完了後に復元される(
        self, page: Page, base_url: str, e2e_data_dir: Path
    ) -> None:
        # Given: テーブル TSV が存在する
        tsv = (
            "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
            "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        )
        (e2e_data_dir / "users.tsv").write_text(tsv, encoding="utf-8")
        page.goto(base_url)

        # When: "ER 図の再作成" ボタンをクリックして完了を待つ
        page.locator('button[aria-label="ER 図の再作成"]').click()
        expect(page.locator("#er-diagram .mermaid")).to_be_visible(timeout=10000)

        # Then: 再作成ボタンが元の状態（有効・回転なし）に戻る
        btn = page.locator('button[aria-label="ER 図の再作成"]')
        expect(btn).to_be_enabled()
        expect(btn.locator("img.spinning")).not_to_be_visible()


class TestDeleteTable:
    """テーブル削除（htmx hx-delete + hx-confirm）。"""

    def test_削除で確認ダイアログが表示される(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタンをクリックする
        dialog_messages: list[str] = []
        page.on("dialog", _capture_and_dismiss(dialog_messages))
        row = page.locator("#table-list tbody tr", has_text="users")
        row.locator("button", has_text="削除").click()

        # Then: 確認ダイアログが表示される
        page.wait_for_timeout(500)
        assert len(dialog_messages) == 1
        assert "users" in dialog_messages[0]
        assert "削除" in dialog_messages[0]

    def test_削除キャンセルで行が残る(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタン → ダイアログでキャンセルする
        page.on("dialog", lambda d: d.dismiss())
        row = page.locator("#table-list tbody tr", has_text="users")
        row.locator("button", has_text="削除").click()

        # Then: 行が残っている
        page.wait_for_timeout(500)
        expect(page.locator("#table-list tbody tr", has_text="users")).to_be_visible()

    def test_削除承認で行が消える(
        self, page: Page, base_url: str, create_table: Callable[..., None]
    ) -> None:
        # Given: テーブル "users" が存在しトップページを表示中
        create_table("users")
        page.goto(base_url)

        # When: 削除ボタン → ダイアログで受け入れる
        page.on("dialog", lambda d: d.accept())
        row = page.locator("#table-list tbody tr", has_text="users")
        row.locator("button", has_text="削除").click()

        # Then: "users" 行が DOM から消える
        expect(page.locator("#table-list tbody tr", has_text="users")).not_to_be_visible()
