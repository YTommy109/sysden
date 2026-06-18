import uuid

from fastapi.testclient import TestClient


def test_root_returns_html(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_project_page_404_for_unknown(client: TestClient) -> None:
    resp = client.get(f"/projects/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_document_page_404_for_unknown(client: TestClient) -> None:
    resp = client.get(f"/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_root_page_contains_project_list_element(client: TestClient) -> None:
    resp = client.get("/")
    assert b"sysden" in resp.content or b"project" in resp.content.lower()
