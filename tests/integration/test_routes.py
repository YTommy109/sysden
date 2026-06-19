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
    monkeypatch.setattr(ai_service, "get_client", lambda: make_fake_openai_client())


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


def test_delete_table_404(client: TestClient) -> None:
    # Given: テーブルが存在しない

    # When: 存在しないテーブルの削除 API にリクエストを送る
    resp = client.delete("/api/tables/nonexistent")

    # Then: 404 が返る
    assert resp.status_code == 404
