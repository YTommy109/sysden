import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_project(client: TestClient) -> None:
    resp = client.post("/api/projects", json={"name": "My Project", "description": "desc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Project"
    assert "id" in data


def test_create_project_missing_name(client: TestClient) -> None:
    resp = client.post("/api/projects", json={"description": "no name"})
    assert resp.status_code == 422


def test_create_ai_job_for_new_document(client: TestClient) -> None:
    # First create a project
    proj = client.post(
        "/api/projects", json={"name": "Proj", "description": ""}
    ).json()
    proj_id = proj["id"]

    with patch("app.routers.api.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: None
        resp = client.post(
            f"/api/projects/{proj_id}/ai-jobs",
            json={"prompt": "新しい設計書を作ってください"},
        )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data


def test_get_ai_job_status(client: TestClient) -> None:
    proj = client.post(
        "/api/projects", json={"name": "P2", "description": ""}
    ).json()
    proj_id = proj["id"]

    with patch("app.routers.api.asyncio") as mock_asyncio:
        mock_asyncio.create_task = lambda coro: None
        job_resp = client.post(
            f"/api/projects/{proj_id}/ai-jobs",
            json={"prompt": "test"},
        ).json()
    job_id = job_resp["job_id"]

    resp = client.get(f"/api/ai-jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_rollback_document(client: TestClient) -> None:
    resp = client.post(
        f"/api/documents/{uuid.uuid4()}/rollback",
        json={"revision_id": str(uuid.uuid4())},
    )
    # non-existent document → 404
    assert resp.status_code == 404
