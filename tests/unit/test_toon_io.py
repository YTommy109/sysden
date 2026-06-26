from pathlib import Path

import pytest

from app import toon_io
from app.models import Column, IndexDocument, TableMeta, TableSummary, ToonDocument


def test_Columnモデルを生成できる() -> None:
    # Arrange & Act
    col = Column(
        symbol="COLUMN_0001",
        logical_name="商品ID",
        physical_name="product_id",
        type="uuid",
        nullable="NO",
        pk="YES",
        unique="YES",
        default="gen_random_uuid()",
        fk_target="",
        description="商品を一意に識別する",
    )

    # Assert
    assert col.symbol == "COLUMN_0001"
    assert col.physical_name == "product_id"


def test_Columnのdefaultとfk_targetは省略可能() -> None:
    # Arrange & Act
    col = Column(
        symbol="COLUMN_0001",
        logical_name="名前",
        physical_name="name",
        type="varchar(100)",
        nullable="NO",
        pk="NO",
        unique="NO",
    )

    # Assert
    assert col.default == ""
    assert col.fk_target == ""
    assert col.description == ""


def test_ToonDocumentを生成できる() -> None:
    # Arrange
    meta = TableMeta(
        symbol="TABLE_0001",
        logical_name="ユーザー",
        physical_name="users",
        description="テスト用",
    )
    col = Column(
        symbol="COLUMN_0001",
        logical_name="識別子",
        physical_name="id",
        type="uuid",
        nullable="NO",
        pk="YES",
        unique="YES",
    )

    # Act
    doc = ToonDocument(meta=meta, columns=[col])

    # Assert
    assert doc.meta.symbol == "TABLE_0001"
    assert len(doc.columns) == 1
    assert doc.logical is None
    assert doc.physical is None
    assert doc.doa is None


def test_IndexDocumentを生成できる() -> None:
    # Arrange & Act
    index = IndexDocument(
        description="テスト",
        rules=["ルール1"],
        tables=[
            TableSummary(
                symbol="TABLE_0001",
                name="users",
                logical_name="ユーザー",
                description="テスト用",
            )
        ],
        er_diagram="erDiagram\n    TABLE_0001",
    )

    # Assert
    assert len(index.tables) == 1
    assert index.tables[0].symbol == "TABLE_0001"
    assert len(index.rules) == 1


# --- toon_io パース / シリアライズ ---

SAMPLE_TABLE_TOON = """\
meta:
  symbol: TABLE_0001
  logical_name: ユーザー
  physical_name: users
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,,,主キー
"""

SAMPLE_TABLE_WITH_DERIVED_TOON = """\
meta:
  symbol: TABLE_0001
  logical_name: ユーザー
  physical_name: users
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,,,主キー

logical[1]{カラム名,型,ユニーク,説明}:
  識別子,UUID,,主キー

physical[1]{column_name,type,nullable,pk,unique,default,description}:
  id,uuid,NO,YES,YES,,主キー

doa[1]{column_name,python_type,required,min,max,max_length,description}:
  id,UUID,YES,,,,主キー
"""

SAMPLE_INDEX_TOON = """\
meta:
  description: テーブル設計インデックス

rules:
  - すべてのテーブルはサロゲートキーとして uuidv7 の id カラムを持つ

tables[1]{symbol,name,logical_name,description}:
  TABLE_0001,users,ユーザー,テスト用テーブル

er_diagram:
  erDiagram
    TABLE_0001["ユーザー"]
"""

MULTI_TABLE_TOON = """\
meta:
  logical_name: 注文
  physical_name: orders
  description: 注文テーブル

columns[2]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,注文ID,order_id,uuid,NO,YES,YES,gen_random_uuid(),,
  COLUMN_0002,注文者,user_id,uuid,NO,NO,NO,,TABLE_0001,ユーザーへの参照

meta:
  logical_name: 配送先
  physical_name: shipping_addresses
  description: 配送先テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,配送先ID,shipping_address_id,uuid,NO,YES,YES,gen_random_uuid(),,
"""


def test_テーブルTOONをパースする() -> None:
    # Arrange & Act
    doc = toon_io.parse_table_toon(SAMPLE_TABLE_TOON)

    # Assert
    assert doc.meta.symbol == "TABLE_0001"
    assert doc.meta.logical_name == "ユーザー"
    assert doc.meta.physical_name == "users"
    assert len(doc.columns) == 1
    assert doc.columns[0].symbol == "COLUMN_0001"
    assert doc.columns[0].type == "uuid"
    assert doc.columns[0].pk == "YES"
    assert doc.columns[0].description == "主キー"


def test_導出セクション付きTOONをパースする() -> None:
    # Arrange & Act
    doc = toon_io.parse_table_toon(SAMPLE_TABLE_WITH_DERIVED_TOON)

    # Assert
    assert doc.logical is not None
    assert len(doc.logical) == 1
    assert doc.logical[0]["カラム名"] == "識別子"
    assert doc.physical is not None
    assert doc.physical[0]["column_name"] == "id"
    assert doc.doa is not None
    assert doc.doa[0]["python_type"] == "UUID"


def test_インデックスTOONをパースする() -> None:
    # Arrange & Act
    index = toon_io.parse_index_toon(SAMPLE_INDEX_TOON)

    # Assert
    assert index.description == "テーブル設計インデックス"
    assert len(index.rules) == 1
    assert "サロゲートキー" in index.rules[0]
    assert len(index.tables) == 1
    assert index.tables[0].symbol == "TABLE_0001"
    assert index.tables[0].name == "users"
    assert "erDiagram" in index.er_diagram


def test_複数テーブルのTOONをパースする() -> None:
    # Arrange & Act
    docs = toon_io.parse_toon_tables(MULTI_TABLE_TOON)

    # Assert
    assert len(docs) == 2
    assert docs[0].meta.physical_name == "orders"
    assert docs[0].columns[1].fk_target == "TABLE_0001"
    assert docs[1].meta.physical_name == "shipping_addresses"


def test_ToonDocumentをシリアライズしてラウンドトリップする() -> None:
    # Arrange
    doc = toon_io.parse_table_toon(SAMPLE_TABLE_TOON)

    # Act
    text = toon_io.serialize_table_toon(doc)
    doc2 = toon_io.parse_table_toon(text)

    # Assert
    assert doc2.meta.symbol == doc.meta.symbol
    assert doc2.meta.logical_name == doc.meta.logical_name
    assert len(doc2.columns) == len(doc.columns)
    assert doc2.columns[0].symbol == doc.columns[0].symbol


def test_IndexDocumentをシリアライズしてラウンドトリップする() -> None:
    # Arrange
    index = toon_io.parse_index_toon(SAMPLE_INDEX_TOON)

    # Act
    text = toon_io.serialize_index_toon(index)
    index2 = toon_io.parse_index_toon(text)

    # Assert
    assert index2.description == index.description
    assert index2.rules == index.rules
    assert len(index2.tables) == len(index.tables)
    assert index2.tables[0].symbol == index.tables[0].symbol


def test_空フィールドを含むカラムのラウンドトリップ() -> None:
    # Arrange — default, fk_target, description が空のカラム
    toon_text = """\
meta:
  symbol: TABLE_0001
  logical_name: テスト
  physical_name: test
  description: テスト

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,名前,name,varchar(100),NO,NO,NO,,,
"""

    # Act
    doc = toon_io.parse_table_toon(toon_text)

    # Assert
    assert doc.columns[0].default == ""
    assert doc.columns[0].fk_target == ""
    assert doc.columns[0].description == ""

    # Act — ラウンドトリップ
    text = toon_io.serialize_table_toon(doc)
    doc2 = toon_io.parse_table_toon(text)
    assert doc2.columns[0].default == ""


# --- ファイル読み書き ---


def test_TOONファイルの書き込みと読み込み(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    meta = TableMeta(
        symbol="TABLE_0001",
        logical_name="ユーザー",
        physical_name="users",
        description="テスト用",
    )
    col = Column(
        symbol="COLUMN_0001",
        logical_name="識別子",
        physical_name="id",
        type="uuid",
        nullable="NO",
        pk="YES",
        unique="YES",
    )
    doc = ToonDocument(meta=meta, columns=[col])

    # Act
    toon_io.write_toon("users", doc)
    loaded = toon_io.read_toon("users")

    # Assert
    assert loaded.meta.symbol == "TABLE_0001"
    assert loaded.columns[0].physical_name == "id"


def test_存在しないTOONの読み込みはFileNotFoundError(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))

    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        toon_io.read_toon("nonexistent")


def test_インデックスTOONファイルが存在しなければデフォルトを返す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))

    # Act
    index = toon_io.read_index_toon()

    # Assert
    assert index.tables == []
    assert index.rules == []
    assert index.er_diagram == ""


def test_インデックスTOONの書き込みと読み込み(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    index = IndexDocument(
        description="テスト",
        rules=["ルール1"],
        tables=[
            TableSummary(
                symbol="TABLE_0001",
                name="users",
                logical_name="ユーザー",
                description="テスト用",
            )
        ],
        er_diagram='erDiagram\n    TABLE_0001["ユーザー"]',
    )

    # Act
    toon_io.write_index_toon(index)
    loaded = toon_io.read_index_toon()

    # Assert
    assert loaded.description == "テスト"
    assert loaded.rules == ["ルール1"]
    assert len(loaded.tables) == 1
    assert loaded.tables[0].name == "users"
    assert "erDiagram" in loaded.er_diagram
