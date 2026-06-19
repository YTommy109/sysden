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


def test_tables_to_er_diagram_fk_relationship() -> None:
    # Arrange — orders.user_id が users テーブルを参照する
    users_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    orders_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "user_id\tUUID\tNO\tNO\tNO\t\t注文者\n"
    )
    table_service.write_tsv("users", users_tsv)
    table_service.write_tsv("orders", orders_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — users → orders のリレーションが含まれる
    assert "users" in result
    assert "orders" in result
    assert "||--o{" in result


def test_tables_to_er_diagram_nullable_fk() -> None:
    # Arrange — orders.coupon_id が nullable で coupons を参照する
    coupons_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    orders_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "coupon_id\tUUID\tYES\tNO\tNO\t\tクーポン\n"
    )
    table_service.write_tsv("coupons", coupons_tsv)
    table_service.write_tsv("orders", orders_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — nullable なので |o--o{ になる
    assert "|o--o{" in result


def test_tables_to_er_diagram_no_matching_table() -> None:
    # Arrange — category_id があるが categories テーブルは存在しない
    products_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "category_id\tUUID\tNO\tNO\tNO\t\tカテゴリ\n"
    )
    table_service.write_tsv("products", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — 参照先がないのでリレーション線は出ない
    assert "||--o{" not in result
    assert "|o--o{" not in result


def test_tables_to_er_diagram_singular_table_match() -> None:
    # Arrange — items.order_id → order テーブル（単数形で一致）
    order_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    items_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "order_id\tUUID\tNO\tNO\tNO\t\t注文\n"
    )
    table_service.write_tsv("order", order_tsv)
    table_service.write_tsv("items", items_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert "||--o{" in result


def test_list_tables_excludes_index(sample_tsv: str) -> None:
    # Arrange — index.tsv が存在する状態
    table_service.write_tsv("users", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.list_tables()

    # Assert — index は含まれない
    assert "index" not in result
    assert "users" in result


def test_rebuild_index_creates_files(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)

    # Act
    table_service.rebuild_index()

    # Assert — index.tsv と index.mmd が生成される
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert (d / "index.mmd").exists()


def test_rebuild_index_empty() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_index()

    # Assert — 空でもファイルは生成される（ヘッダのみ / 空文字列）
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert (d / "index.mmd").exists()


def test_read_index_tables(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.read_index_tables()

    # Assert — ソート済みのテーブル名リスト
    assert result == ["orders", "users"]


def test_read_index_tables_empty() -> None:
    # Arrange — テーブルなしで index を構築
    table_service.rebuild_index()

    # Act
    result = table_service.read_index_tables()

    # Assert
    assert result == []


def test_read_index_tables_no_file() -> None:
    # Arrange — index.tsv が存在しない

    # Act
    result = table_service.read_index_tables()

    # Assert — ファイルがなければ空リスト
    assert result == []


def test_read_er_diagram(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.read_er_diagram()

    # Assert
    assert "erDiagram" in result
    assert "users" in result


def test_read_er_diagram_empty() -> None:
    # Arrange — テーブルなしで index を構築
    table_service.rebuild_index()

    # Act
    result = table_service.read_er_diagram()

    # Assert
    assert result == ""


def test_read_er_diagram_no_file() -> None:
    # Arrange — index.mmd が存在しない

    # Act
    result = table_service.read_er_diagram()

    # Assert — ファイルがなければ空文字列
    assert result == ""
