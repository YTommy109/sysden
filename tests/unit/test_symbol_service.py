from pathlib import Path

import pytest
import yaml

from app import symbol_service
from app.models import Column, TableMeta, ToonDocument


def _make_doc(
    physical_name: str = "test",
    logical_name: str = "テスト",
    symbol: str = "",
    columns: list[Column] | None = None,
) -> ToonDocument:
    meta = TableMeta(
        symbol=symbol,
        logical_name=logical_name,
        physical_name=physical_name,
        description="テスト用",
    )
    if columns is None:
        columns = [
            Column(
                symbol="COLUMN_0001",
                logical_name="識別子",
                physical_name="id",
                type="uuid",
                nullable="NO",
                pk="YES",
                unique="YES",
            )
        ]
    return ToonDocument(meta=meta, columns=columns)


def test_最初のテーブルシンボルはTABLE_0001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — index.yaml が存在しない
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))

    # Act
    symbol = symbol_service.allocate_table_symbol()

    # Assert
    assert symbol == "TABLE_0001"


def test_連続で採番すると連番になる(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange — 1 回目の採番
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    s1 = symbol_service.allocate_table_symbol()

    # Act — 2 回目の採番
    s2 = symbol_service.allocate_table_symbol()

    # Assert
    assert s1 == "TABLE_0001"
    assert s2 == "TABLE_0002"


def test_既存のindex_yamlから採番を継続する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — next_table_id: 5 の index.yaml を用意
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    (tmp_path / "index.yaml").write_text(yaml.dump({"next_table_id": 5}), encoding="utf-8")

    # Act
    symbol = symbol_service.allocate_table_symbol()

    # Assert
    assert symbol == "TABLE_0005"

    # Assert — index.yaml が更新されている
    data = yaml.safe_load((tmp_path / "index.yaml").read_text(encoding="utf-8"))
    assert data["next_table_id"] == 6


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (3, ["COLUMN_0001", "COLUMN_0002", "COLUMN_0003"]),
        (0, []),
    ],
)
def test_カラムシンボルの生成(count: int, expected: list[str]) -> None:
    # Act
    symbols = symbol_service.allocate_column_symbols(count)

    # Assert
    assert symbols == expected


def test_プレースホルダをリマップする() -> None:
    # Arrange — NEW_1 を fk_target に持つカラム
    col_with_fk = Column(
        symbol="COLUMN_0002",
        logical_name="注文者",
        physical_name="user_id",
        type="uuid",
        nullable="NO",
        pk="NO",
        unique="NO",
        fk_target="NEW_1",
    )
    doc = _make_doc(
        physical_name="orders",
        columns=[
            Column(
                symbol="COLUMN_0001",
                logical_name="注文ID",
                physical_name="order_id",
                type="uuid",
                nullable="NO",
                pk="YES",
                unique="YES",
            ),
            col_with_fk,
        ],
    )
    symbol_map = {"NEW_1": "TABLE_0003"}

    # Act
    result = symbol_service.remap_placeholders([doc], symbol_map)

    # Assert
    assert result[0].columns[1].fk_target == "TABLE_0003"


def test_プレースホルダなしならそのまま返る() -> None:
    # Arrange — fk_target が既存シンボル
    col = Column(
        symbol="COLUMN_0001",
        logical_name="注文者",
        physical_name="user_id",
        type="uuid",
        nullable="NO",
        pk="NO",
        unique="NO",
        fk_target="TABLE_0001",
    )
    doc = _make_doc(columns=[col])
    symbol_map: dict[str, str] = {}

    # Act
    result = symbol_service.remap_placeholders([doc], symbol_map)

    # Assert
    assert result[0].columns[0].fk_target == "TABLE_0001"


def test_metaのシンボルを設定する() -> None:
    # Arrange — symbol が空の doc
    doc = _make_doc(symbol="")

    # Act
    result = symbol_service.remap_placeholders([doc], {}, table_symbols=["TABLE_0010"])

    # Assert
    assert result[0].meta.symbol == "TABLE_0010"
