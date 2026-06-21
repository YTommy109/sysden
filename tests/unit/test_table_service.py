import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app import table_service
from app.table_service import _translate_type


def test_テーブルが空ならリストも空() -> None:
    # Arrange — 空のデータディレクトリ（conftest が tmp_path を設定済み）

    # Act
    result = table_service.list_tables()

    # Assert
    assert result == []


def test_TSVの書き込みと読み込み(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    rows = table_service.read_tsv("users")

    # Assert
    assert rows[0]["column_name"] == "id"
    assert rows[0]["type"] == "UUID"


@pytest.mark.parametrize(
    "read_func",
    [table_service.read_tsv, table_service.read_tsv_raw],
    ids=["read_tsv", "read_tsv_raw"],
)
def test_存在しないテーブルのTSV読み込みはFileNotFoundError(
    read_func: Callable[..., Any],
) -> None:
    # Arrange — テーブルが存在しない状態

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        read_func("nonexistent")


def test_TSVを生文字列で読み込む(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    content = table_service.read_tsv_raw("users")

    # Assert
    assert "column_name\t" in content
    assert "id\tUUID" in content


def test_テーブルを削除する(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("orders", sample_tsv)

    # Act
    table_service.delete_table("orders")

    # Assert
    assert not table_service.table_exists("orders")


def test_存在しないテーブルの削除はFileNotFoundError() -> None:
    # Arrange — テーブルが存在しない状態

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.delete_table("nonexistent")


def test_TSVをMarkdownテーブルに変換する() -> None:
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


def test_必須カラムの型に必須マークが付く() -> None:
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


def test_PKカラム名が太字になる() -> None:
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


@pytest.mark.parametrize(
    ("input_type", "expected"),
    [
        ("DATE", "日付"),
        ("VARCHAR", "文字列"),
        ("VARCHAR(255)", "文字列(255)"),
        ("DECIMAL", "固定小数点数"),
        ("DECIMAL(10,2)", "固定小数点数(10,2)"),
        ("INTEGER", "整数"),
        ("INT", "整数"),
        ("BIGINT", "整数"),
        ("SMALLINT", "整数"),
        ("TEXT", "テキスト"),
        ("BOOLEAN", "真偽値"),
        ("TIMESTAMPTZ", "タイムスタンプ"),
        ("TIMESTAMP", "タイムスタンプ"),
        ("UUID", "UUID"),
        ("CUSTOM_TYPE", "CUSTOM_TYPE"),
    ],
)
def test_型名が日本語に変換される(input_type: str, expected: str) -> None:
    assert _translate_type(input_type) == expected


def test_FKカラムにfkクラスが付く(sample_tsv: str) -> None:
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


def test_非FKカラムにfkクラスは付かない() -> None:
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


def test_説明にデフォルトプレフィックスが付かない() -> None:
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


def test_空リストでプレースホルダを返す() -> None:
    # Arrange — 空リスト

    # Act
    result = table_service.tsv_to_markdown([])

    # Assert
    assert result == "_（カラム定義なし）_"


def test_テーブルの存在確認(sample_tsv: str) -> None:
    # Arrange — テーブルが存在しない状態
    assert not table_service.table_exists("foo")

    # Act
    table_service.write_tsv("foo", sample_tsv)

    # Assert
    assert table_service.table_exists("foo")


def test_テーブルなしでER図は空文字列() -> None:
    # Arrange — テーブルが存在しない

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert result == ""


def test_単一テーブルのER図(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert result.startswith("erDiagram")
    assert "users" in result


def test_複数テーブルのER図(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.write_tsv("orders", sample_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert
    assert "users" in result
    assert "orders" in result


def test_FK関係がER図に含まれる() -> None:
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


def test_nullableなFKはオプショナル線になる() -> None:
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


def test_参照先テーブルがなければリレーション線なし() -> None:
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


def test_単数形テーブル名でFK一致() -> None:
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


def test_descriptionのテーブル参照でFK検出() -> None:
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


def test_表示名経由のテーブル参照でFK検出() -> None:
    # Arrange — description に日本語表示名「商品種類テーブル」と記述、
    #           ファイル名は英語 product_types
    product_types_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
    )
    products_tsv = (
        "column_name\ttype\tnullable\tpk\tunique\tdefault\tdescription\n"
        "id\tUUID\tNO\tYES\tYES\t\t主キー\n"
        "種類識別子\tUUID\tNO\tNO\tNO\t\t商品種類テーブルの識別子を参照\n"
    )
    table_service.write_tsv("product_types", product_types_tsv)
    table_service.write_markdown("product_types", "# 商品種類\n\n![[product_types.tsv]]")
    table_service.write_tsv("products", products_tsv)

    # Act
    result = table_service.tables_to_er_diagram()

    # Assert — 表示名経由で product_types → products のリレーションが検出される
    assert "product_types" in result
    assert "products" in result
    assert "||--o{" in result


def test_descriptionの参照先がなければリレーション線なし() -> None:
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


def test_idサフィックスがdescription参照より優先() -> None:
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


def test_テーブル一覧にindexは含まれない(sample_tsv: str) -> None:
    # Arrange — index.tsv が存在する状態
    table_service.write_tsv("users", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.list_tables()

    # Assert — index は含まれない
    assert "index" not in result
    assert "users" in result


def test_インデックス再構築でファイルが生成される(sample_tsv: str) -> None:
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


def test_テーブルなしでもインデックスファイルが生成される() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_index()

    # Assert — 空でもファイルは生成される（ヘッダのみ / 空文字列）
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert (d / "index.mmd").exists()


def test_インデックスからテーブル一覧を読み込む(sample_tsv: str) -> None:
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


def test_空のインデックスは空リスト() -> None:
    # Arrange — テーブルなしで index を構築
    table_service.rebuild_index()

    # Act
    result = table_service.read_index_tables()

    # Assert
    assert result == []


def test_インデックスファイルがなければ空リスト() -> None:
    # Arrange — index.tsv が存在しない

    # Act
    result = table_service.read_index_tables()

    # Assert — ファイルがなければ空リスト
    assert result == []


def test_ER図を読み込む(sample_tsv: str) -> None:
    # Arrange
    table_service.write_tsv("users", sample_tsv)
    table_service.rebuild_index()

    # Act
    result = table_service.read_er_diagram()

    # Assert
    assert "erDiagram" in result
    assert "users" in result


def test_テーブルなしのER図は空文字列() -> None:
    # Arrange — テーブルなしで index を構築
    table_service.rebuild_index()

    # Act
    result = table_service.read_er_diagram()

    # Assert
    assert result == ""


def test_ER図ファイルがなければ空文字列() -> None:
    # Arrange — index.mmd が存在しない

    # Act
    result = table_service.read_er_diagram()

    # Assert — ファイルがなければ空文字列
    assert result == ""


def test_テーブル一覧再構築でTSVが生成される(sample_tsv: str) -> None:
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


def test_テーブルなしでもテーブル一覧TSVが生成される() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_index_tables()

    # Assert — 空でもファイルは生成される（ヘッダのみ）
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.tsv").exists()
    assert table_service.read_index_tables() == []


def test_ER図再構築でmmdファイルが生成される(sample_tsv: str) -> None:
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


def test_テーブルなしでも空のmmdファイルが生成される() -> None:
    # Arrange — テーブルが存在しない

    # Act
    table_service.rebuild_er_diagram_file()

    # Assert — テーブルなしでも空文字列が書き込まれる
    from app.config import get_data_dir

    d = get_data_dir()
    assert (d / "index.mmd").exists()
    assert table_service.read_er_diagram() == ""


def test_Markdownの書き込みと読み込み() -> None:
    # Arrange
    content = "# users\n\nユーザー管理テーブル。\n\n![[users.tsv]]"

    # Act
    table_service.write_markdown("users", content)
    result = table_service.read_markdown("users")

    # Assert
    assert result == content


def test_存在しないMarkdownはNone() -> None:
    # Arrange — markdown が存在しない

    # Act
    result = table_service.read_markdown("nonexistent")

    # Assert
    assert result is None


def test_埋め込みTSVがMarkdownテーブルに展開される(sample_tsv: str) -> None:
    # Arrange — TSV を書き込み、埋め込みリンクを含む markdown を用意
    table_service.write_tsv("users", sample_tsv)
    content = "# users\n\n説明文。\n\n![[users.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — ![[users.tsv]] が markdown テーブルに展開される
    assert "![[users.tsv]]" not in result
    assert "| カラム名 |" in result
    assert "| **id** |" in result


def test_埋め込みなしのMarkdownはそのまま返る() -> None:
    # Arrange — 埋め込みリンクがない markdown
    content = "# users\n\n説明文のみ。"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — そのまま返る
    assert result == content


def test_存在しないTSVの埋め込みはプレースホルダになる() -> None:
    # Arrange — 参照先の TSV が存在しない
    content = "# missing\n\n![[missing.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — 埋め込みはプレースホルダになる
    assert "![[missing.tsv]]" not in result
    assert "missing.tsv" in result


def test_パストラバーサルの埋め込みは展開されない() -> None:
    # Arrange — パストラバーサルを含む埋め込みリンク
    content = "# test\n\n![[../../etc/passwd.tsv]]"

    # Act
    result = table_service.render_markdown_with_embeds(content)

    # Assert — パストラバーサルは展開されない（そのまま残る）
    assert "![[../../etc/passwd.tsv]]" in result


def test_テーブル削除で物理設計ファイルも削除される(tmp_path: Path) -> None:
    # Given: 論理設計と物理設計の両方が存在する
    table_service.write_tsv("users", "column_name\ttype\nid\tUUID\n")
    table_service.write_physical_tsv("users", "column_name\ttype\nid\tuuid\n")
    table_service.write_physical_doa_tsv("users", "column_name\tpython_type\nid\tUUID\n")
    table_service.write_physical_markdown("users", "# 物理設計\n")

    # When: テーブルを削除する
    table_service.delete_table("users")

    # Then: 物理設計ファイルも削除される
    assert not table_service.physical_design_exists("users")
    assert table_service.read_physical_markdown("users") is None
    assert not (tmp_path / "physical_users_doa.tsv").exists()


def test_テーブル削除でMarkdownも削除される(sample_tsv: str) -> None:
    # Arrange — TSV と markdown の両方を作成
    table_service.write_tsv("orders", sample_tsv)
    table_service.write_markdown("orders", "# orders\n\n![[orders.tsv]]")

    # Act
    table_service.delete_table("orders")

    # Assert — TSV も markdown も削除される
    assert not table_service.table_exists("orders")
    assert table_service.read_markdown("orders") is None


def test_Markdownの見出しから表示名を取得する() -> None:
    # Arrange — h1 日本語見出しを持つ markdown
    table_service.write_markdown(
        "products", "# プロダクト\n\n## 概要\n\n説明。\n\n![[products.tsv]]"
    )

    # Act
    result = table_service.read_table_display_name("products")

    # Assert
    assert result == "プロダクト"


@pytest.mark.parametrize(
    ("name", "md_content"),
    [
        ("missing", None),
        ("notes", "## 概要\n\n本文のみ。"),
    ],
    ids=["Markdownなし", "h1見出しなし"],
)
def test_表示名が取得できない場合はファイル名を返す(name: str, md_content: str | None) -> None:
    # Arrange
    if md_content is not None:
        table_service.write_markdown(name, md_content)

    # Act
    result = table_service.read_table_display_name(name)

    # Assert — ファイル名をそのまま返す
    assert result == name


def test_タイトル見出しを除去する() -> None:
    # Arrange
    content = "# プロダクト\n\n## 概要\n\n説明文。"

    # Act
    result = table_service.strip_title_heading(content)

    # Assert — h1 が除去され、概要セクションから始まる
    assert "# プロダクト" not in result
    assert result.startswith("## 概要")


def test_h1がなければそのまま返る() -> None:
    # Arrange — h1 がない場合はそのまま返る
    content = "## 概要\n\n説明文。"

    # Act
    result = table_service.strip_title_heading(content)

    # Assert
    assert result == content


def test_テーブル一覧がphysicalプレフィックスを除外する(tmp_path: Path) -> None:
    # Given: 論理設計と物理設計の TSV が混在する
    (tmp_path / "users.tsv").write_text("column_name\ttype\n", encoding="utf-8")
    (tmp_path / "physical_users.tsv").write_text("column_name\ttype\n", encoding="utf-8")
    (tmp_path / "physical_users_doa.tsv").write_text("column_name\tpython_type\n", encoding="utf-8")

    # When: テーブル一覧を取得する
    result = table_service.list_tables()

    # Then: physical_ プレフィックスのファイルは含まれない
    assert result == ["users"]


def test_物理設計の存在判定(tmp_path: Path) -> None:
    # Given: 物理設計ファイルが存在しない
    assert table_service.physical_design_exists("users") is False

    # When: 物理設計 TSV を書き込む
    table_service.write_physical_tsv("users", "column_name\ttype\nid\tuuid\n")

    # Then: 存在判定が True になる
    assert table_service.physical_design_exists("users") is True


def test_物理設計markdownの読み書き(tmp_path: Path) -> None:
    # Given: 物理設計 markdown が存在しない
    assert table_service.read_physical_markdown("users") is None

    # When: 物理設計 markdown を書き込む
    table_service.write_physical_markdown("users", "# テーブル定義\n\n![[physical_users.tsv]]")

    # Then: 読み込みで内容が取得できる
    result = table_service.read_physical_markdown("users")
    assert result is not None
    assert "![[physical_users.tsv]]" in result


def test_物理設計DoA_TSVの書き込み(tmp_path: Path) -> None:
    # Given: データディレクトリが存在する

    # When: DoA TSV を書き込む
    content = "column_name\tpython_type\trequired\nid\tUUID\tYES\n"
    table_service.write_physical_doa_tsv("users", content)

    # Then: ファイルが作成される
    path = tmp_path / "physical_users_doa.tsv"
    assert path.exists()
    assert "UUID" in path.read_text(encoding="utf-8")


def test_テーブル一覧に表示名が含まれる(sample_tsv: str) -> None:
    # Arrange — markdown 付きテーブルを作成
    table_service.write_tsv("products", sample_tsv)
    table_service.write_markdown("products", "# プロダクト\n\n## 概要\n\n![[products.tsv]]")

    # Act
    table_service.rebuild_index_tables()

    # Assert — display_name が日本語になる
    tables = table_service.read_index_tables()
    assert tables[0]["name"] == "products"
    assert tables[0]["display_name"] == "プロダクト"


def test_Markdownなしの表示名はファイル名(sample_tsv: str) -> None:
    # Arrange — markdown なしのテーブル
    table_service.write_tsv("users", sample_tsv)

    # Act
    table_service.rebuild_index_tables()

    # Assert — display_name はファイル名と同じ
    tables = table_service.read_index_tables()
    assert tables[0]["name"] == "users"
    assert tables[0]["display_name"] == "users"


class TestTableServiceLogging:
    """テーブルサービスのログ出力検証。"""

    def test_TSV書き込み時にテーブル名がログ出力される(
        self, sample_tsv: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Act
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.write_tsv("users", sample_tsv)

        # Assert
        assert "TSV 書き込み: table=users" in caplog.text

    def test_テーブル削除時にテーブル名がログ出力される(
        self, sample_tsv: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arrange
        table_service.write_tsv("orders", sample_tsv)

        # Act
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.delete_table("orders")

        # Assert
        assert "テーブル削除: table=orders" in caplog.text

    def test_存在しないテーブル削除で警告ログが出る(self, caplog: pytest.LogCaptureFixture) -> None:
        # Act
        with (
            caplog.at_level(logging.WARNING, logger="app.table_service"),
            pytest.raises(FileNotFoundError),
        ):
            table_service.delete_table("nonexistent")

        # Assert
        assert "テーブル削除失敗: table=nonexistent" in caplog.text

    def test_Markdown書き込み時にテーブル名がログ出力される(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Act
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.write_markdown("users", "# users\n\n説明")

        # Assert
        assert "Markdown 書き込み: table=users" in caplog.text

    def test_インデックス再構築完了がログ出力される(self, caplog: pytest.LogCaptureFixture) -> None:
        # Act
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.rebuild_index()

        # Assert
        assert "インデックス再構築完了" in caplog.text
