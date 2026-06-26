import logging

import pytest

from app import table_service
from app.models import Column, TableMeta, ToonDocument
from app.toon_io import parse_table_toon

SAMPLE_TOON = """\
meta:
  symbol: TABLE_0001
  logical_name: ユーザー
  physical_name: users
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,,,主キー
"""


def _make_column(**overrides: str) -> Column:
    defaults = {
        "symbol": "COLUMN_0001",
        "logical_name": "テスト",
        "physical_name": "test",
        "type": "varchar(100)",
        "nullable": "NO",
        "pk": "NO",
        "unique": "NO",
        "default": "",
        "fk_target": "",
        "description": "",
    }
    defaults.update(overrides)
    return Column(**defaults)


# ── 導出ロジック ──


@pytest.mark.parametrize(
    ("sql_type", "expected"),
    [
        ("uuid", "UUID"),
        ("varchar(100)", "文字列(100)"),
        ("varchar(255)", "文字列(255)"),
        ("integer", "整数"),
        ("int", "整数"),
        ("bigint", "整数"),
        ("smallint", "整数"),
        ("decimal(10,2)", "固定小数点数(10,2)"),
        ("text", "テキスト"),
        ("boolean", "真偽値"),
        ("date", "日付"),
        ("timestamp", "タイムスタンプ"),
        ("timestamptz", "タイムスタンプ"),
        ("custom_type", "custom_type"),
    ],
)
def test_論理設計で型名が日本語に変換される(sql_type: str, expected: str) -> None:
    # Arrange
    col = _make_column(type=sql_type, logical_name="テスト")

    # Act
    result = table_service.derive_logical([col])

    # Assert
    assert result[0]["型"] == expected


def test_論理設計で日本語カラム名が使われる() -> None:
    # Arrange
    col = _make_column(logical_name="商品名", type="varchar(100)")

    # Act
    result = table_service.derive_logical([col])

    # Assert
    assert result[0]["カラム名"] == "商品名"


def test_論理設計でユニークフラグが変換される() -> None:
    # Arrange
    col_yes = _make_column(unique="YES")
    col_no = _make_column(unique="NO")

    # Act
    result = table_service.derive_logical([col_yes, col_no])

    # Assert
    assert result[0]["ユニーク"] == "○"
    assert result[1]["ユニーク"] == ""


def test_物理設計でphysical_nameが使われる() -> None:
    # Arrange
    col = _make_column(physical_name="product_id", type="uuid")

    # Act
    result = table_service.derive_physical([col])

    # Assert
    assert result[0]["column_name"] == "product_id"
    assert result[0]["type"] == "uuid"


def test_物理設計で全フィールドが含まれる() -> None:
    # Arrange
    col = _make_column(
        physical_name="id",
        type="uuid",
        nullable="NO",
        pk="YES",
        unique="YES",
        default="gen_random_uuid()",
        description="主キー",
    )

    # Act
    result = table_service.derive_physical([col])

    # Assert
    row = result[0]
    assert row["nullable"] == "NO"
    assert row["pk"] == "YES"
    assert row["unique"] == "YES"
    assert row["default"] == "gen_random_uuid()"
    assert row["description"] == "主キー"


@pytest.mark.parametrize(
    ("sql_type", "expected_python_type"),
    [
        ("uuid", "UUID"),
        ("varchar(100)", "str"),
        ("text", "str"),
        ("integer", "int"),
        ("int", "int"),
        ("bigint", "int"),
        ("smallint", "int"),
        ("boolean", "bool"),
        ("decimal(10,2)", "Decimal"),
        ("date", "date"),
        ("timestamp", "datetime"),
        ("timestamptz", "datetime"),
    ],
)
def test_DoAでSQL型がPython型に変換される(sql_type: str, expected_python_type: str) -> None:
    # Arrange
    col = _make_column(type=sql_type, physical_name="test_col")

    # Act
    result = table_service.derive_doa([col])

    # Assert
    assert result[0]["python_type"] == expected_python_type


def test_DoAでvarcharのmax_lengthが抽出される() -> None:
    # Arrange
    col = _make_column(type="varchar(100)", physical_name="name")

    # Act
    result = table_service.derive_doa([col])

    # Assert
    assert result[0]["max_length"] == "100"


def test_DoAでnullableがrequiredに変換される() -> None:
    # Arrange
    col_required = _make_column(nullable="NO")
    col_optional = _make_column(nullable="YES")

    # Act
    result = table_service.derive_doa([col_required, col_optional])

    # Assert
    assert result[0]["required"] == "YES"
    assert result[1]["required"] == "NO"


def test_derive_allで3セクションが追加される() -> None:
    # Arrange
    doc = parse_table_toon(SAMPLE_TOON)

    # Act
    result = table_service.derive_all(doc)

    # Assert
    assert result.logical is not None
    assert result.physical is not None
    assert result.doa is not None
    assert len(result.logical) == 1
    assert len(result.physical) == 1
    assert len(result.doa) == 1


# ── CRUD ──


def test_テーブルが空ならリストも空() -> None:
    # Act
    result = table_service.list_tables()

    # Assert
    assert result == []


def test_テーブルの存在確認() -> None:
    # Arrange
    assert not table_service.table_exists("users")
    doc = parse_table_toon(SAMPLE_TOON)

    # Act
    table_service.save_table("users", doc)

    # Assert
    assert table_service.table_exists("users")


def test_テーブルの保存と取得() -> None:
    # Arrange
    doc = parse_table_toon(SAMPLE_TOON)

    # Act
    table_service.save_table("users", doc)
    loaded = table_service.get_table("users")

    # Assert
    assert loaded.meta.symbol == "TABLE_0001"
    assert loaded.columns[0].physical_name == "id"


def test_存在しないテーブルの取得はFileNotFoundError() -> None:
    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.get_table("nonexistent")


def test_テーブルを削除する() -> None:
    # Arrange
    doc = parse_table_toon(SAMPLE_TOON)
    table_service.save_table("users", doc)

    # Act
    table_service.delete_table("users")

    # Assert
    assert not table_service.table_exists("users")


def test_存在しないテーブルの削除はFileNotFoundError() -> None:
    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        table_service.delete_table("nonexistent")


# ── テーブル名バリデーション ──


@pytest.mark.parametrize(
    "name",
    ["users", "order_items", "a", "users2", "t" * 64],
)
def test_正当なテーブル名(name: str) -> None:
    assert table_service.validate_table_name(name) is True


@pytest.mark.parametrize(
    "name",
    [".hidden", "has space", "UPPER", "123start", "a" * 65, "-dash"],
)
def test_不正なテーブル名(name: str) -> None:
    assert table_service.validate_table_name(name) is False


# ── ER 図 ──


def test_テーブルなしでER図は空文字列() -> None:
    # Act
    result = table_service.generate_er_diagram()

    # Assert
    assert result == ""


def test_FK関係がER図に含まれる() -> None:
    # Arrange — users と orders（orders.user_id → TABLE_0001）
    users = ToonDocument(
        meta=TableMeta(
            symbol="TABLE_0001",
            logical_name="ユーザー",
            physical_name="users",
            description="",
        ),
        columns=[_make_column(symbol="COLUMN_0001", physical_name="id", type="uuid")],
    )
    orders = ToonDocument(
        meta=TableMeta(
            symbol="TABLE_0002",
            logical_name="注文",
            physical_name="orders",
            description="",
        ),
        columns=[
            _make_column(symbol="COLUMN_0001", physical_name="order_id", type="uuid"),
            _make_column(
                symbol="COLUMN_0002",
                physical_name="user_id",
                type="uuid",
                fk_target="TABLE_0001",
            ),
        ],
    )
    table_service.save_table("users", users)
    table_service.save_table("orders", orders)
    table_service.rebuild_index()

    # Act
    result = table_service.generate_er_diagram()

    # Assert
    assert "erDiagram" in result
    assert "TABLE_0001" in result
    assert "TABLE_0002" in result
    assert "||--o{" in result


def test_nullableなFKはオプショナル線になる() -> None:
    # Arrange
    users = ToonDocument(
        meta=TableMeta(
            symbol="TABLE_0001",
            logical_name="ユーザー",
            physical_name="users",
            description="",
        ),
        columns=[_make_column(physical_name="id", type="uuid")],
    )
    orders = ToonDocument(
        meta=TableMeta(
            symbol="TABLE_0002",
            logical_name="注文",
            physical_name="orders",
            description="",
        ),
        columns=[
            _make_column(
                physical_name="coupon_id",
                type="uuid",
                nullable="YES",
                fk_target="TABLE_0001",
            ),
        ],
    )
    table_service.save_table("users", users)
    table_service.save_table("orders", orders)
    table_service.rebuild_index()

    # Act
    result = table_service.generate_er_diagram()

    # Assert
    assert "|o--o{" in result


# ── インデックス ──


def test_インデックス再構築でテーブル一覧が更新される() -> None:
    # Arrange
    doc = parse_table_toon(SAMPLE_TOON)
    table_service.save_table("users", doc)

    # Act
    table_service.rebuild_index()

    # Assert
    tables = table_service.list_tables()
    assert len(tables) == 1
    assert tables[0].name == "users"
    assert tables[0].symbol == "TABLE_0001"


def test_テーブルなしでもインデックスが生成される() -> None:
    # Act
    table_service.rebuild_index()

    # Assert
    tables = table_service.list_tables()
    assert tables == []


# ── ログ ──


class TestTableServiceLogging:
    def test_テーブル保存時にログ出力される(self, caplog: pytest.LogCaptureFixture) -> None:
        doc = parse_table_toon(SAMPLE_TOON)
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.save_table("users", doc)
        assert "テーブル保存: table=users" in caplog.text

    def test_テーブル削除時にログ出力される(self, caplog: pytest.LogCaptureFixture) -> None:
        doc = parse_table_toon(SAMPLE_TOON)
        table_service.save_table("users", doc)
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.delete_table("users")
        assert "テーブル削除: table=users" in caplog.text

    def test_インデックス再構築完了がログ出力される(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.rebuild_index()
        assert "インデックス再構築完了" in caplog.text
