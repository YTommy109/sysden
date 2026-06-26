import pytest
from fastapi.testclient import TestClient

from app import table_service
from app.toon_io import parse_table_toon
from tests.conftest import SAMPLE_TOON


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")


def _save_sample_table() -> None:
    doc = parse_table_toon(SAMPLE_TOON)
    doc = table_service.derive_all(doc)
    table_service.save_table("users", doc)
    table_service.rebuild_index()


def test_トップページがHTMLを返す(client: TestClient) -> None:
    # Arrange: アプリが起動している

    # Act: トップページにアクセスする
    resp = client.get("/")

    # Assert: HTML が 200 で返る
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_存在しないテーブルの詳細は404(client: TestClient) -> None:
    # Arrange: 存在しないテーブル名

    # Act: テーブル詳細ページにアクセスする
    resp = client.get("/tables/nonexistent")

    # Assert: 404 が返る
    assert resp.status_code == 404


def test_テーブル詳細ページにタブが含まれる(client: TestClient) -> None:
    # Arrange
    _save_sample_table()

    # Act
    resp = client.get("/tables/users")

    # Assert
    assert resp.status_code == 200
    assert "論理設計" in resp.text
    assert "物理設計" in resp.text
    assert "DoA" in resp.text
    assert "ユーザー" in resp.text


def test_AI経由でテーブルを作成する(client: TestClient, mock_openai: None) -> None:
    # Arrange: AI モックが TOON を返す状態でデータディレクトリが空

    # Act: テーブル作成 API にリクエストを送る
    resp = client.post(
        "/api/tables",
        data={"prompt": "テーブルを作って"},
        follow_redirects=True,
    )

    # Assert: 200 が返りテーブルが作成される
    assert resp.status_code == 200
    assert table_service.table_exists("stub_table")


def test_同名テーブル作成で409(client: TestClient, mock_openai: None) -> None:
    # Arrange: stub_table をあらかじめ作成しておく
    client.post("/api/tables", data={"prompt": "テーブルを作って"}, follow_redirects=True)
    assert table_service.table_exists("stub_table")

    # Act: 同じ stub_table をもう一度作成しようとする
    resp = client.post(
        "/api/tables",
        data={"prompt": "テーブルを作って"},
        follow_redirects=False,
    )

    # Assert: 409 が返る
    assert resp.status_code == 409


def test_存在しないテーブルの更新は404(client: TestClient, mock_openai: None) -> None:
    # Arrange: 存在しないテーブル名（有効な形式だが未作成）

    # Act: 存在しないテーブルの更新 API にリクエストを送る
    resp = client.post("/api/tables/nonexistent_table", data={"prompt": "更新"})

    # Assert: 404 が返る
    assert resp.status_code == 404


def test_AI経由でテーブルを更新する(client: TestClient, mock_openai: None) -> None:
    # Arrange: テーブルが存在する
    _save_sample_table()

    # Act: テーブル更新 API にリクエストを送る
    resp = client.post(
        "/api/tables/users",
        data={"prompt": "カラムを追加"},
        follow_redirects=True,
    )

    # Assert: 200 が返る
    assert resp.status_code == 200


def test_テーブルを削除する(client: TestClient) -> None:
    # Arrange: テーブルが存在する
    _save_sample_table()

    # Act: テーブル削除 API にリクエストを送る
    resp = client.delete("/api/tables/users")

    # Assert: 削除成功レスポンスが返り、テーブルが存在しない
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "name": "users"}
    assert not table_service.table_exists("users")


def test_存在しないテーブルの削除は404(client: TestClient) -> None:
    # Arrange: テーブルが存在しない

    # Act: 存在しないテーブルの削除 API にリクエストを送る
    resp = client.delete("/api/tables/nonexistent")

    # Assert: 404 が返る
    assert resp.status_code == 404


class TestTableNameValidation:
    @pytest.mark.parametrize("name", [".hidden", "UPPER", "123start"])
    def test_不正なテーブル名の更新は422(
        self, client: TestClient, mock_openai: None, name: str
    ) -> None:
        # Arrange: 不正なテーブル名

        # Act: 不正な名前でテーブル更新 API にリクエストを送る
        resp = client.post(f"/api/tables/{name}", data={"prompt": "テスト"})

        # Assert: 422 が返る
        assert resp.status_code == 422

    @pytest.mark.parametrize("name", [".hidden", "UPPER", "123start"])
    def test_不正なテーブル名の削除は422(self, client: TestClient, name: str) -> None:
        # Arrange: 不正なテーブル名

        # Act: 不正な名前でテーブル削除 API にリクエストを送る
        resp = client.delete(f"/api/tables/{name}")

        # Assert: 422 が返る
        assert resp.status_code == 422


class TestHtmxHxRedirect:
    HX_HEADERS = {"HX-Request": "true"}

    def test_テーブル作成でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None
    ) -> None:
        # Arrange: AI モックが有効な状態

        # Act: HX-Request ヘッダー付きでテーブル作成する
        resp = client.post(
            "/api/tables",
            data={"prompt": "テスト"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )

        # Assert: 200 + HX-Redirect ヘッダーが返る
        assert resp.status_code == 200
        assert "HX-Redirect" in resp.headers

    def test_テーブル更新でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None
    ) -> None:
        # Arrange: テーブルが存在する
        _save_sample_table()

        # Act: HX-Request ヘッダー付きでテーブル更新する
        resp = client.post(
            "/api/tables/users",
            data={"prompt": "カラムを追加"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )

        # Assert: 200 + HX-Redirect ヘッダーが返る
        assert resp.status_code == 200
        assert "/tables/users" in resp.headers["HX-Redirect"]


class TestSseEndpoints:
    @pytest.mark.parametrize(
        "url",
        ["/api/sse/rebuild-index", "/api/sse/rebuild-er"],
    )
    def test_SSEエンドポイントがイベントストリームを返す(
        self, client: TestClient, url: str
    ) -> None:
        # Arrange: アプリが起動している

        # Act: SSE エンドポイントに GET する
        with client.stream("GET", url) as resp:
            # Assert: text/event-stream が返る
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = b"".join(resp.iter_bytes()).decode()
            assert "event: complete" in body
