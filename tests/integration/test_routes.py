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


def test_index_returns_html(client: TestClient) -> None:
    # Given: アプリが起動している

    # When: トップページにアクセスする
    resp = client.get("/")

    # Then: HTML が 200 で返る
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_table_detail_404(client: TestClient) -> None:
    # Given: 存在しないテーブル名

    # When: テーブル詳細ページにアクセスする
    resp = client.get("/tables/nonexistent")

    # Then: 404 が返る
    assert resp.status_code == 404


def test_create_table_via_ai(
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


def test_table_detail_renders_markdown(
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


def test_table_detail_shows_display_name(
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


def test_table_detail_without_markdown(
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


def test_create_table_conflict(
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


def test_update_table_via_ai(
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


def test_update_table_404(client: TestClient, mock_openai: None) -> None:
    # Given: テーブルが存在しない

    # When: 存在しないテーブルの更新 API にリクエストを送る
    resp = client.post(
        "/api/tables/nonexistent",
        data={"prompt": "カラムを追加"},
    )

    # Then: 404 が返る
    assert resp.status_code == 404


def test_delete_table(
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


def test_create_multiple_tables_via_ai(
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


def test_create_multiple_tables_conflict(
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


def test_delete_table_404(client: TestClient) -> None:
    # Given: テーブルが存在しない

    # When: 存在しないテーブルの削除 API にリクエストを送る
    resp = client.delete("/api/tables/nonexistent")

    # Then: 404 が返る
    assert resp.status_code == 404


def test_rebuild_index_tables(client: TestClient, sample_tsv: str) -> None:
    # Given: テーブルが存在するが index.tsv がない
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: テーブル一覧再作成 API にリクエストを送る
    resp = client.post("/api/rebuild-index-tables", follow_redirects=True)

    # Then: 200 が返り index.tsv が生成される
    assert resp.status_code == 200
    names = [t["name"] for t in table_service.read_index_tables()]
    assert names == ["users"]


def test_rebuild_er_diagram(client: TestClient, sample_tsv: str) -> None:
    # Given: テーブルが存在するが index.mmd がない
    from app import table_service

    table_service.write_tsv("users", sample_tsv)

    # When: ER 図再作成 API にリクエストを送る
    resp = client.post("/api/rebuild-er-diagram", follow_redirects=True)

    # Then: 200 が返り ER 図が生成される
    assert resp.status_code == 200
    er = table_service.read_er_diagram()
    assert "erDiagram" in er
