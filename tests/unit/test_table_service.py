from app import table_service


def test_list_tables_empty() -> None:
    assert table_service.list_tables() == []


def test_write_and_read_tsv() -> None:
    tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    table_service.write_tsv("users", tsv)
    rows = table_service.read_tsv("users")
    assert rows[0]["column_name"] == "id"
    assert rows[0]["type"] == "UUID"


def test_delete_table() -> None:
    tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    table_service.write_tsv("orders", tsv)
    table_service.delete_table("orders")
    assert not table_service.table_exists("orders")


def test_tsv_to_markdown() -> None:
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
    md = table_service.tsv_to_markdown(rows)
    assert "| id |" in md
    assert "| UUID |" in md
    assert "---" in md


def test_tsv_to_markdown_empty() -> None:
    assert table_service.tsv_to_markdown([]) == "_（カラム定義なし）_"


def test_table_exists() -> None:
    assert not table_service.table_exists("foo")
    table_service.write_tsv(
        "foo", "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
    )
    assert table_service.table_exists("foo")
