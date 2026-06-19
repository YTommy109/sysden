from pathlib import Path
from types import SimpleNamespace

import pytest

SAMPLE_TSV = (
    "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
)


def make_fake_openai_client(
    tsv: str = SAMPLE_TSV,
    calls: list[dict] | None = None,
) -> SimpleNamespace:
    """OpenAI API 構造を模倣するスタブクライアントを生成する。"""

    def create(**kwargs: object) -> SimpleNamespace:
        if calls is not None:
            calls.append(kwargs)
        choice = SimpleNamespace(message=SimpleNamespace(content=tsv))
        return SimpleNamespace(choices=[choice])

    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


@pytest.fixture()
def sample_tsv() -> str:
    """テスト用の最小限カラム定義 TSV。"""
    return SAMPLE_TSV


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全テストで一時データディレクトリと API キーを設定する。"""
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
