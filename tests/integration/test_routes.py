import pytest
from fastapi.testclient import TestClient

from app import ai_service
from tests.conftest import make_fake_openai_client


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient を返す。"""
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI クライアントをスタブに差し替え、固定 TSV を返す。"""
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")


def test_トップページがHTMLを返す(client: TestClient) -> None:
    # Given: アプリが起動している

    # When: トップページにアクセスする
    resp = client.get("/")

    # Then: HTML が 200 で返る
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_存在しないテーブルの詳細は404(client: TestClient) -> None:
    # Given: 存在しないテーブル名

    # When: テーブル詳細ページにアクセスする
    resp = client.get("/tables/nonexistent")

    # Then: 404 が返る
    assert resp.status_code == 404


def test_AI経由でテーブルを作成する(
    client: TestClient,
    mock_openai: None,
) -> None:
    # Given: AI モックが TSV を返す状態でデータディレクトリが空

    # When: テーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"name": "users", "prompt": "ユーザーテーブルを作って"},
        follow_redirects=True,
    )

    # Then: 200 が返りテーブル名がレスポンスに含まれる
    assert resp.status_code == 200
    assert "users" in resp.text

    # Then: markdown ファイルも作成される
    from app import table_service

    md = table_service.read_markdown("users")
    assert md is not None


def test_詳細ページでMarkdownがレンダリングされる(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: TSV と markdown の両方が存在するテーブル
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown(
        "users",
        "# ユーザー\n\n## 概要\n\nユーザー管理。\n\n## テーブル設計\n\n![[users.tsv]]",
    )

    # When: 詳細ページにアクセスする
    resp = client.get("/tables/users")

    # Then: markdown の内容と TSV テーブルの両方がレンダリングされる
    assert resp.status_code == 200
    assert "ユーザー管理" in resp.text
    assert "カラム名" in resp.text


def test_詳細ページに日本語表示名が表示される(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: 日本語見出しの markdown 付きテーブル
    from app import table_service

    table_service.write_tsv("products", sample_tsv)
    table_service.write_markdown(
        "products",
        "# プロダクト\n\n## 概要\n\n商品情報。\n\n## テーブル設計\n\n![[products.tsv]]",
    )

    # When: 詳細ページにアクセスする
    resp = client.get("/tables/products")

    # Then: h1 と title に日本語表示名が使われる
    assert resp.status_code == 200
    assert ">プロダクト</h1>" in resp.text
    assert "プロダクト — sysden" in resp.text


def test_Markdownなしの詳細ページでTSVのみ表示(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: TSV のみ存在するテーブル（markdown なし）
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: 詳細ページにアクセスする
    resp = client.get("/tables/users")

    # Then: TSV テーブルのみ表示される（後方互換）
    assert resp.status_code == 200
    assert "カラム名" in resp.text


def test_同名テーブル作成で409(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: 同名テーブルが既に存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: 同名でテーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"name": "users", "prompt": "ユーザーテーブルを作って"},
    )

    # Then: 409 Conflict が返る
    assert resp.status_code == 409


def test_AI経由でテーブルを更新する(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: テーブルが既に存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: テーブル更新 API にリクエストを送る
    resp = client.post(
        "/api/tables/users",
        data={"prompt": "email カラムを追加して"},
        follow_redirects=True,
    )

    # Then: 200 が返りテーブル名がレスポンスに含まれる
    assert resp.status_code == 200
    assert "users" in resp.text


def test_存在しないテーブルの更新は404(client: TestClient, mock_openai: None) -> None:
    # Given: テーブルが存在しない

    # When: 存在しないテーブルの更新 API にリクエストを送る
    resp = client.post(
        "/api/tables/nonexistent",
        data={"prompt": "カラムを追加"},
    )

    # Then: 404 が返る
    assert resp.status_code == 404


def test_テーブルを削除する(
    client: TestClient,
    sample_tsv: str,
) -> None:
    # Given: テーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: テーブル削除 API にリクエストを送る
    resp = client.delete("/api/tables/users")

    # Then: 削除成功レスポンスが返る
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "name": "users"}


def test_AI経由で複数テーブルを作成する(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: AI モックが 2 テーブルの [name] 形式を返す
    multi_response = (
        "[users]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[users.md]\n"
        "# users\n\n![[users.tsv]]\n"
        "\n"
        "[orders]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[orders.md]\n"
        "# orders\n\n![[orders.tsv]]\n"
    )
    fake = make_fake_openai_client(tsv=multi_response)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # When: name なしでテーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"prompt": "ユーザーと注文テーブルを作って"},
        follow_redirects=True,
    )

    # Then: トップページにリダイレクトされ両テーブルが存在する
    assert resp.status_code == 200
    from app import table_service

    assert table_service.table_exists("users")
    assert table_service.table_exists("orders")
    assert table_service.read_markdown("users") is not None
    assert table_service.read_markdown("orders") is not None


def test_複数テーブル作成で既存テーブルと競合(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_tsv: str,
) -> None:
    # Given: "orders" が既に存在し、AI が users + orders を返す
    from app import table_service

    table_service.write_tsv("orders", sample_tsv)

    multi_response = (
        "[users]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[users.md]\n"
        "# users\n\n![[users.tsv]]\n"
        "\n"
        "[orders]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[orders.md]\n"
        "# orders\n\n![[orders.tsv]]\n"
    )
    fake = make_fake_openai_client(tsv=multi_response)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # When: name なしでテーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"prompt": "ユーザーと注文テーブルを作って"},
    )

    # Then: 409 Conflict が返り、users は作成されない
    assert resp.status_code == 409
    assert not table_service.table_exists("users")


def test_存在しないテーブルの削除は404(client: TestClient) -> None:
    # Given: テーブルが存在しない

    # When: 存在しないテーブルの削除 API にリクエストを送る
    resp = client.delete("/api/tables/nonexistent")

    # Then: 404 が返る
    assert resp.status_code == 404


class TestTableNameValidation:
    """テーブル名バリデーション — パストラバーサル防止。"""

    @pytest.mark.parametrize(
        "name",
        [
            ".hidden",
            "has space",
            "UPPER",
            "123start",
            "a" * 65,
            "-dash",
        ],
    )
    def test_不正なテーブル名の作成は422(
        self, client: TestClient, mock_openai: None, name: str
    ) -> None:
        # Given: 不正なテーブル名

        # When: 不正な名前でテーブル作成 API にリクエストを送る
        resp = client.post(
            "/api/tables",
            data={"name": name, "prompt": "テスト"},
        )

        # Then: 422 が返る
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "name",
        [".hidden", "UPPER", "123start"],
    )
    def test_不正なテーブル名の更新は422(
        self, client: TestClient, mock_openai: None, name: str
    ) -> None:
        # Given: 不正なテーブル名（スラッシュなし — スラッシュ含みはルーティングで 404）

        # When: 不正な名前でテーブル更新 API にリクエストを送る
        resp = client.post(
            f"/api/tables/{name}",
            data={"prompt": "カラムを追加"},
        )

        # Then: 422 が返る
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "name",
        [".hidden", "UPPER", "123start"],
    )
    def test_不正なテーブル名の削除は422(self, client: TestClient, name: str) -> None:
        # Given: 不正なテーブル名（スラッシュなし — スラッシュ含みはルーティングで 404）

        # When: 不正な名前でテーブル削除 API にリクエストを送る
        resp = client.delete(f"/api/tables/{name}")

        # Then: 422 が返る
        assert resp.status_code == 422

    def test_スラッシュ含みのパストラバーサルはルーターで拒否(self, client: TestClient) -> None:
        # Given: スラッシュ含みのパストラバーサル名

        # When: スラッシュ含みの名前で API にリクエストを送る
        resp = client.post("/api/tables/../etc/passwd", data={"prompt": "test"})

        # Then: ルーティングレベルで拒否される（ハンドラに到達しない）
        assert resp.status_code in (404, 405)

    @pytest.mark.parametrize(
        "name",
        ["users", "order_items", "a", "users2", "t" * 64],
    )
    def test_正当なテーブル名は受け入れられる(
        self, client: TestClient, mock_openai: None, name: str
    ) -> None:
        # Given: 正当なテーブル名

        # When: 正当な名前でテーブル作成 API にリクエストを送る
        resp = client.post(
            "/api/tables",
            data={"name": name, "prompt": "テスト"},
            follow_redirects=True,
        )

        # Then: 422 以外が返る（作成成功）
        assert resp.status_code != 422


def test_複数テーブル作成の書き込み失敗でロールバック(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: AI が 2 テーブルを返すが、2 件目の書き込みで失敗する
    from app import table_service
    from app.main import app

    multi_response = (
        "[users]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[users.md]\n"
        "# users\n\n![[users.tsv]]\n"
        "\n"
        "[orders]\n"
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "\n"
        "[orders.md]\n"
        "# orders\n\n![[orders.tsv]]\n"
    )
    fake = make_fake_openai_client(tsv=multi_response)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    call_count = 0
    original_write_tsv = table_service.write_tsv

    def failing_write_tsv(name: str, content: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise OSError("disk full")
        original_write_tsv(name, content)

    monkeypatch.setattr(table_service, "write_tsv", failing_write_tsv)

    # When: テーブル作成 API にリクエストを送る
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    resp = no_raise_client.post(
        "/api/tables",
        data={"prompt": "ユーザーと注文テーブルを作って"},
    )

    # Then: 500 が返り、1 件目のテーブルもロールバックされている
    assert resp.status_code == 500
    assert not table_service.table_exists("users")
    assert not table_service.table_exists("orders")


class TestHtmxHxRedirect:
    """HX-Request ヘッダー付きリクエストで HX-Redirect が返る。"""

    HX_HEADERS = {"HX-Request": "true"}

    def test_テーブル作成でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None
    ) -> None:
        # Given: AI モックが有効な状態

        # When: HX-Request ヘッダー付きでテーブル作成する
        resp = client.post(
            "/api/tables",
            data={"name": "users", "prompt": "テスト"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )

        # Then: 200 + HX-Redirect ヘッダーが返る
        assert resp.status_code == 200
        assert "/tables/users" in resp.headers["HX-Redirect"]

    def test_テーブル更新でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None, sample_tsv: str
    ) -> None:
        # Given: テーブルが存在する
        from app import table_service

        table_service.write_tsv("users", sample_tsv)

        # When: HX-Request ヘッダー付きでテーブル更新する
        resp = client.post(
            "/api/tables/users",
            data={"prompt": "カラムを追加"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )

        # Then: 200 + HX-Redirect ヘッダーが返る
        assert resp.status_code == 200
        assert "/tables/users" in resp.headers["HX-Redirect"]

    @pytest.mark.parametrize(
        ("url", "target"),
        [
            ("/api/rebuild-index-tables", "#index-body"),
            ("/api/rebuild-er-diagram", "#er-diagram"),
        ],
    )
    def test_リビルドでSSEフラグメントを返す(
        self, client: TestClient, url: str, target: str
    ) -> None:
        # Given: アプリが起動している

        # When: HX-Request ヘッダー付きでリビルドする
        resp = client.post(url, headers=self.HX_HEADERS, follow_redirects=False)

        # Then: SSE 接続用の HTML フラグメントが返る
        assert resp.status_code == 200
        body = resp.text
        assert "sse-connect=" in body
        assert f'hx-target="{target}"' in body
        assert 'class="spinning"' in body
        assert "disabled" in body


class TestSseEndpoints:
    """SSE エンドポイントの統合テスト。"""

    @pytest.mark.parametrize(
        "url",
        ["/api/sse/rebuild-index", "/api/sse/rebuild-er"],
    )
    def test_SSEエンドポイントがイベントストリームを返す(
        self, client: TestClient, url: str
    ) -> None:
        # Given: アプリが起動している

        # When: SSE エンドポイントに GET する
        with client.stream("GET", url) as resp:
            # Then: text/event-stream が返る
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            # Then: complete イベントが含まれる
            body = b"".join(resp.iter_bytes()).decode()
            assert "event: complete" in body
            assert "data: done" in body

    @pytest.mark.parametrize(
        ("url", "func_name"),
        [
            ("/api/sse/rebuild-index", "rebuild_index"),
            ("/api/sse/rebuild-er", "rebuild_er_diagram_file"),
        ],
    )
    def test_エラー時もSSEイベントが送信される(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        url: str,
        func_name: str,
    ) -> None:
        # Given: 対象関数が例外を投げる状態
        from app import table_service

        def _failing() -> None:
            msg = "disk full"
            raise OSError(msg)

        monkeypatch.setattr(table_service, func_name, _failing)

        # When: SSE エンドポイントに GET する
        with client.stream("GET", url) as resp:
            # Then: 例外が発生しても complete イベントが返る（回転を停止できる）
            assert resp.status_code == 200
            body = b"".join(resp.iter_bytes()).decode()
            assert "event: complete" in body


def test_物理設計を生成する(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: 論理設計のテーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown(
        "users",
        "# ユーザー\n\n## 概要\n\nユーザー管理。\n\n## テーブル設計\n\n![[users.tsv]]",
    )

    # When: 物理設計生成 API にリクエストを送る
    resp = client.post("/api/tables/users/physical", follow_redirects=False)

    # Then: 物理設計ページにリダイレクトされる
    assert resp.status_code == 303
    assert "/tables/users/physical" in resp.headers["location"]

    # Then: 物理設計ファイルが作成される
    assert table_service.physical_design_exists("users")


def test_論理設計が存在しないテーブルの物理設計生成は404(
    client: TestClient,
    mock_openai: None,
) -> None:
    # Given: テーブルが存在しない

    # When: 物理設計生成 API にリクエストを送る
    resp = client.post("/api/tables/nonexistent/physical")

    # Then: 404 が返る
    assert resp.status_code == 404


def test_物理設計生成でHXリダイレクトを返す(
    client: TestClient,
    mock_openai: None,
    sample_tsv: str,
) -> None:
    # Given: テーブルが存在する
    from app import table_service

    table_service.write_tsv("users", sample_tsv)
    table_service.write_markdown("users", "# ユーザー\n\n![[users.tsv]]")

    # When: HX-Request ヘッダー付きで物理設計を生成する
    resp = client.post(
        "/api/tables/users/physical",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    # Then: 200 + HX-Redirect ヘッダーが返る
    assert resp.status_code == 200
    assert "/tables/users/physical" in resp.headers["HX-Redirect"]


def test_テーブル一覧を再作成する(client: TestClient, sample_tsv: str) -> None:
    # Given: テーブルが存在するが index.tsv がない
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: テーブル一覧再作成 API にリクエストを送る
    resp = client.post("/api/rebuild-index-tables", follow_redirects=True)

    # Then: 200 が返り index.tsv が生成される
    assert resp.status_code == 200
    names = [t["name"] for t in table_service.read_index_tables()]
    assert names == ["users"]


def test_ER図を再作成する(client: TestClient, sample_tsv: str) -> None:
    # Given: テーブルが存在するが index.mmd がない
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: ER 図再作成 API にリクエストを送る
    resp = client.post("/api/rebuild-er-diagram", follow_redirects=True)

    # Then: 200 が返り ER 図が生成される
    assert resp.status_code == 200
    er = table_service.read_er_diagram()
    assert "erDiagram" in er
