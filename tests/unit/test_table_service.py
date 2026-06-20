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

    # Assert — 日本語ヘッダー、PK 太字、必須は型に * プレフィックス
    assert "| カラム名 |" in md
    assert "| 型 |" in md
    assert "| 必須 |" not in md
    assert "| ユニーク |" in md
    assert "| 説明 |" in md
    assert "| **id** |" in md
    assert '| <span class="required">*</span> UUID |' in md
    assert "---" in md


def test_tsv_to_markdown_required_prefix_on_type() -> None:
    # Arrange
    rows = [
        {
            "column_name": "id",
            "type": "UUID",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "memo",
            "type": "TEXT",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — nullable=NO → 型に * プレフィックス、nullable=YES → そのまま
    lines = md.split("\n")
    id_line = next(line for line in lines if "| id |" in line)
    memo_line = next(line for line in lines if "| memo |" in line)
    assert '| <span class="required">*</span> UUID |' in id_line
    assert "| テキスト |" in memo_line


def test_tsv_to_markdown_pk_makes_column_name_bold() -> None:
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
        },
        {
            "column_name": "name",
            "type": "VARCHAR(100)",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "ユーザー名",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — PK カラムは太字、非 PK は素のまま
    assert "| **id** |" in md
    assert "| name |" in md


def test_tsv_to_markdown_translates_types() -> None:
    # Arrange
    rows = [
        {
            "column_name": "a",
            "type": "DATE",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "b",
            "type": "VARCHAR(255)",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "c",
            "type": "DECIMAL(10,2)",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "d",
            "type": "INTEGER",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "e",
            "type": "TEXT",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "f",
            "type": "BOOLEAN",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "g",
            "type": "TIMESTAMPTZ",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
        {
            "column_name": "h",
            "type": "UUID",
            "nullable": "YES",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — 型が日本語に変換される（パラメータは保持）
    assert "| 日付 |" in md
    assert "| 文字列(255) |" in md
    assert "| 固定小数点数(10,2) |" in md
    assert "| 整数 |" in md
    assert "| テキスト |" in md
    assert "| 真偽値 |" in md
    assert "| タイムスタンプ |" in md
    assert "| UUID |" in md


def test_tsv_to_markdown_fk_column_has_fk_class(sample_tsv: str) -> None:
    # Arrange — users テーブルを作成して user_id カラムを持つ行を表示
    table_service.write_tsv("users", sample_tsv)
    rows = [
        {
            "column_name": "user_id",
            "type": "UUID",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — FK カラム名が fk クラスの span で囲まれる
    assert '<span class="fk">user_id</span>' in md


def test_tsv_to_markdown_non_fk_column_no_fk_class() -> None:
    # Arrange — FK でない通常カラム
    rows = [
        {
            "column_name": "name",
            "type": "VARCHAR(100)",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "",
            "description": "",
        },
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — fk クラスは付かない
    assert "fk" not in md


def test_tsv_to_markdown_description_without_default_prefix() -> None:
    # Arrange
    rows = [
        {
            "column_name": "end_date",
            "type": "DATE",
            "nullable": "NO",
            "pk": "NO",
            "unique": "NO",
            "default": "9999-12-31",
            "description": "発売終了日（未定の場合は 9999-12-31）",
        }
    ]

    # Act
    md = table_service.tsv_to_markdown(rows)

    # Assert — description のみ表示、"デフォルト:" プレフィックスは付かない
    lines = md.split("\n")
    data_line = next(line for line in lines if "end_date" in line)
    assert "発売終了日（未定の場合は 9999-12-31）" in data_line
    assert "デフォルト:" not in data_line


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


def test_tables_to_er_diagram_description_table_reference() -> None:
    # Arrange — 「種類識別子」カラムの description に「商品種類テーブル」と記述
    product_types_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    products_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "種類識別子\tUUID\tNO\tNO\tNO\t\t商品種類テーブルの識別子を参照\n"
    )
    table_service.write_tsv("商品種類", product_types_tsv)
    table_service.write_tsv("プロダクト", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — 商品種類 → プロダクト のリレーションが含まれる
    assert "商品種類" in result
    assert "プロダクト" in result
    assert "||--o{" in result


def test_tables_to_er_diagram_description_no_matching_table() -> None:
    # Arrange — description に「注文テーブル」と書いてあるが注文テーブルは存在しない
    products_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "種類識別子\tUUID\tNO\tNO\tNO\t\t注文テーブルの識別子\n"
    )
    table_service.write_tsv("プロダクト", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — 参照先テーブルがないのでリレーション線は出ない
    assert "||--o{" not in result
    assert "|o--o{" not in result


def test_tables_to_er_diagram_id_suffix_takes_precedence() -> None:
    # Arrange — _id サフィックスと description 両方でリレーションが検出可能な場合
    #           _id サフィックスが優先される
    users_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    categories_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    orders_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "user_id\tUUID\tNO\tNO\tNO\t\tcategoriesテーブルの参照\n"
    )
    table_service.write_tsv("users", users_tsv)
    table_service.write_tsv("categories", categories_tsv)
    table_service.write_tsv("orders", orders_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — _id サフィックスで users に解決される（description の categories ではない）
    assert 'users ||--o{ orders : ""' in result
    assert "categories" not in result.split("\n")[-1]


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

    # Assert — name と display_name を含む辞書のリスト
    assert len(result) == 2
    assert result[0]["name"] == "orders"
    assert result[1]["name"] == "users"


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


def test_rebuild_index_tables_creates_tsv(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)

    # Act
    table_service.rebuild_index_tables()

    # Assert — index.tsv が生成され、index.mmd は生成されない
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert not (d / "index.mmd").exists()
    names = [t["name"] for t in table_service.read_index_tables()]
    assert names == ["orders", "users"]


def test_rebuild_index_tables_empty() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_index_tables()

    # Assert — 空でもファイルは生成される（ヘッダのみ）
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert table_service.read_index_tables() == []


def test_rebuild_er_diagram_file_creates_mmd(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    table_service.rebuild_er_diagram_file()

    # Assert — index.mmd が生成され、index.tsv は生成されない
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.mmd").exists()
    assert not (d / "index.tsv").exists()
    result = table_service.read_er_diagram()
    assert "erDiagram" in result
    assert "users" in result


def test_rebuild_er_diagram_file_empty() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_er_diagram_file()

    # Assert — テーブルなしでも空文字列が書き込まれる
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.mmd").exists()
    assert table_service.read_er_diagram() == ""


def test_write_and_read_markdown() -> None:
    # Arrange
    content = "# users\n\nユーザー管理テーブル。\n\n![[users.tsv]]"

    # Act
    table_service.write_markdown("users", content)
    result = table_service.read_markdown("users")

    # Assert
    assert result == content


def test_read_markdown_not_found() -> None:
    # Arrange — markdown が存在しない

    # Act
    result = table_service.read_markdown("nonexistent")

    # Assert
    assert result is None


def test_render_markdown_with_embeds(sample_tsv: str) -> None:
    # Arrange — TSV を書き込み、埋め込みリンクを含む markdown を用意
    table_service.write_tsv("users", sample_tsv)
    content = "# users\n\n説明文。\n\n![[users.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — ![[users.tsv]] が markdown テーブルに展開される
    assert "![[users.tsv]]" not in result
    assert "| カラム名 |" in result
    assert "| **id** |" in result


def test_render_markdown_with_embeds_no_embed() -> None:
    # Arrange — 埋め込みリンクがない markdown
    content = "# users\n\n説明文のみ。"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — そのまま返る
    assert result == content


def test_render_markdown_with_embeds_missing_tsv() -> None:
    # Arrange — 参照先の TSV が存在しない
    content = "# missing\n\n![[missing.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — 埋め込みはプレースホルダになる
    assert "![[missing.tsv]]" not in result
    assert "missing.tsv" in result


def test_render_markdown_with_embeds_ignores_path_traversal() -> None:
    # Arrange — パストラバーサルを含む埋め込みリンク
    content = "# test\n\n![[../../etc/passwd.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — パストラバーサルは展開されない（そのまま残る）
    assert "![[../../etc/passwd.tsv]]" in result


def test_delete_table_also_deletes_markdown(sample_tsv: str) -> None:
    # Arrange — TSV と markdown の両方を作成
    table_service.write_tsv("orders", sample_tsv)
    table_service.write_markdown("orders", "# orders\n\n![[orders.tsv]]")

    # Act
    table_service.delete_table("orders")

    # Assert — TSV も markdown も削除される
    assert not table_service.table_exists("orders")
    assert table_service.read_markdown("orders") is None


def test_read_table_display_name_from_markdown() -> None:
    # Arrange — 日本語見出しを持つ markdown
    table_service.write_markdown("products", "## プロダクト\n\n説明。\n\n![[products.tsv]]")

    # Act
    result = table_service.read_table_display_name("products")

    # Assert
    assert result == "プロダクト"


def test_read_table_display_name_strips_table_suffix() -> None:
    # Arrange — 「テーブル」サフィックス付きの見出し
    table_service.write_markdown("users", "## ユーザー テーブル\n\n![[users.tsv]]")

    # Act
    result = table_service.read_table_display_name("users")

    # Assert — 「テーブル」が除去される
    assert result == "ユーザー"


def test_read_table_display_name_no_markdown() -> None:
    # Arrange — markdown がない

    # Act
    result = table_service.read_table_display_name("missing")

    # Assert — ファイル名をそのまま返す
    assert result == "missing"


def test_read_table_display_name_no_heading() -> None:
    # Arrange — 見出しがない markdown
    table_service.write_markdown("notes", "本文のみ。")

    # Act
    result = table_service.read_table_display_name("notes")

    # Assert — ファイル名をそのまま返す
    assert result == "notes"


def test_rebuild_index_tables_includes_display_name(sample_tsv: str) -> None:
    # Arrange — markdown 付きテーブルを作成
    table_service.write_tsv("products", sample_tsv)
    table_service.write_markdown("products", "## プロダクト\n\n![[products.tsv]]")

    # Act
    table_service.rebuild_index_tables()

    # Assert — display_name が日本語になる
    tables = table_service.read_index_tables()
    assert tables[0]["name"] == "products"
    assert tables[0]["display_name"] == "プロダクト"


def test_rebuild_index_tables_fallback_display_name(sample_tsv: str) -> None:
    # Arrange — markdown なしのテーブル
    table_service.write_tsv("users", sample_tsv)

    # Act
    table_service.rebuild_index_tables()

    # Assert — display_name はファイル名と同じ
    tables = table_service.read_index_tables()
    assert tables[0]["name"] == "users"
    assert tables[0]["display_name"] == "users"
