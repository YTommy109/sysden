import pytest

from app import table_service


def test_list_tables_empty() -> None:
    # Arrange — 空のデータディレクトリ（conftest が tmp_path を設定済み）

    # Act
    result = table_service.list_tables()

    # Assert
    assert result == []


def test_write_and_read_tsv(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    rows = table_service.read_tsv("users")

    # Assert
    assert rows[0]["column_name"] == "id"
    assert rows[0]["type"] == "UUID"


def test_read_tsv_not_found() -> None:
    # Arrange — テーブルが存在しない状態

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.read_tsv("nonexistent")


def test_read_tsv_raw(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    content = table_service.read_tsv_raw("users")

    # Assert
    assert "column_name\t" in content
    assert "id\tUUID" in content


def test_read_tsv_raw_not_found() -> None:
    # Arrange — テーブルが存在しない状態

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.read_tsv_raw("nonexistent")


def test_delete_table(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("orders", sample_tsv)

    # Act
    table_service.delete_table("orders")

    # Assert
    assert not table_service.table_exists("orders")


def test_delete_table_not_found() -> None:
    # Arrange — テーブルが存在しない状態

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.delete_table("nonexistent")


def test_tsv_to_markdown() -> None:
    # Arrange
    rows = [
        {
            "column_name": "id",
            "type": "UUID",
            "nullable": "NO",
            "pk": "YES",
            "unique": "YES",
            "default": "",
            "description": "主キー",
        }
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert
    assert "| id |" in md
    assert "| UUID |" in md
    assert "---" in md


def test_tsv_to_markdown_empty() -> None:
    # Arrange — 空リスト

    # Act
    result = table_service.tsv_to_markdown([])

    # Assert
    assert result == "_（カラム定義なし）_"


def test_table_exists(sample_tsv: str) -> None:
    # Arrange — テーブルが存在しない状態
    assert not table_service.table_exists("foo")

    # Act
    table_service.write_tsv("foo", sample_tsv)

    # Assert
    assert table_service.table_exists("foo")


def test_tables_to_er_diagram_empty() -> None:
    # Arrange — テーブルが存在しない

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert result == ""


def test_tables_to_er_diagram_single(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert result.startswith("erDiagram")
    assert "users" in result


def test_tables_to_er_diagram_multiple(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert "users" in result
    assert "orders" in result
