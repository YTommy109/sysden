from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_index_returns_html(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_table_detail_404(client: TestClient) -> None:
    resp = client.get("/tables/nonexistent")
    assert resp.status_code == 404


def test_create_table_via_ai(client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    tsv_output = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = tsv_output

    with patch("app.ai_service.OpenAI") as MockOpenAI:
        mock_client_obj = MagicMock()
        MockOpenAI.return_value = mock_client_obj
        mock_client_obj.chat.completions.create.return_value = mock_resp

        resp = client.post(
            "/api/tables",
            data={"name": "users", "prompt": "ユーザーテーブルを作って"},
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert "users" in resp.text
