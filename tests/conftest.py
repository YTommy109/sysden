import pytest


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
