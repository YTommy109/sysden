import os
import socket
import subprocess
import time
from collections.abc import Callable, Generator
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_server(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    msg = f"Server did not start within {timeout}s"
    raise TimeoutError(msg)


@pytest.fixture(scope="session")
def e2e_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("e2e_data")


@pytest.fixture(scope="session")
def e2e_server(e2e_data_dir: Path) -> Generator[str]:
    """E2E テスト用の FastAPI サーバーをサブプロセスで起動する。"""
    port = _find_free_port()
    env = {
        **os.environ,
        "SYSDEN_DATA": str(e2e_data_dir),
        "SYSDEN_TEST_MODE": "1",
        "OPENAI_API_KEY": "test-key",
    }
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(port)],
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    try:
        _wait_for_server(port)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def base_url(e2e_server: str) -> str:
    return e2e_server


@pytest.fixture(autouse=True)
def clean_data(e2e_data_dir: Path) -> None:
    """各テスト前にデータディレクトリの TSV / markdown を削除する。"""
    for f in e2e_data_dir.glob("*.tsv"):
        f.unlink()
    for f in e2e_data_dir.glob("*.mmd"):
        f.unlink()
    for f in e2e_data_dir.glob("*.md"):
        f.unlink()


@pytest.fixture()
def create_table(base_url: str) -> Callable[..., None]:
    """API 経由でテーブルを作成するヘルパー。"""

    def _create(name: str, prompt: str = "テスト用テーブル") -> None:
        resp = httpx.post(
            f"{base_url}/api/tables",
            data={"name": name, "prompt": prompt},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    return _create


@pytest.fixture()
def create_table_auto(base_url: str) -> Callable[..., None]:
    """AI にテーブル名も決めさせてテーブルを作成するヘルパー。"""

    def _create(prompt: str = "テスト用テーブル") -> None:
        resp = httpx.post(
            f"{base_url}/api/tables",
            data={"prompt": prompt},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    return _create
