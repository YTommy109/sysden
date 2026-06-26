import logging
import re

from app.config import get_data_dir
from app.models import Column, TableSummary, ToonDocument
from app.toon_io import (
    read_index_toon,
    read_toon,
    write_index_toon,
    write_toon,
)

logger = logging.getLogger(__name__)

_TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_TYPE_PARAM_RE = re.compile(r"^([a-z]+)(\(.+\))$", re.IGNORECASE)

_TYPE_MAP: dict[str, str] = {
    "uuid": "UUID",
    "varchar": "文字列",
    "integer": "整数",
    "int": "整数",
    "bigint": "整数",
    "smallint": "整数",
    "decimal": "固定小数点数",
    "text": "テキスト",
    "boolean": "真偽値",
    "date": "日付",
    "timestamp": "日時",
    "timestamptz": "日時",
}

_PYTHON_TYPE_MAP: dict[str, str] = {
    "uuid": "UUID",
    "varchar": "str",
    "text": "str",
    "integer": "int",
    "int": "int",
    "bigint": "int",
    "smallint": "int",
    "boolean": "bool",
    "decimal": "Decimal",
    "date": "date",
    "timestamp": "datetime",
    "timestamptz": "datetime",
}


def validate_table_name(name: str) -> bool:
    return _TABLE_NAME_RE.fullmatch(name) is not None


def _split_type(sql_type: str) -> tuple[str, str]:
    m = _TYPE_PARAM_RE.match(sql_type)
    if m:
        return m.group(1).lower(), m.group(2)
    return sql_type.lower(), ""


def derive_logical(columns: list[Column]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for col in columns:
        base, params = _split_type(col.type)
        jp_type = _TYPE_MAP.get(base, col.type) + params
        name = f"* {col.logical_name}" if col.nullable == "NO" else col.logical_name
        rows.append(
            {
                "カラム名": name,
                "型": jp_type,
                "ユニーク": "○" if col.unique.upper() == "YES" else "",
                "説明": col.description,
            }
        )
    return rows


def derive_physical(doc: ToonDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "column_name": "id",
            "type": "uuid",
            "nullable": "NO",
            "pk": "YES",
            "unique": "YES",
            "default": "uuidv7()",
            "description": "サロゲートキー",
        },
    ]
    for col in doc.columns:
        rows.append(
            {
                "column_name": col.physical_name,
                "type": col.type,
                "nullable": col.nullable,
                "pk": col.pk,
                "unique": col.unique,
                "default": col.default,
                "description": col.description,
            }
        )
    rows.extend(
        [
            {
                "column_name": "created_at",
                "type": "timestamptz",
                "nullable": "NO",
                "pk": "NO",
                "unique": "NO",
                "default": "now()",
                "description": "作成日時",
            },
            {
                "column_name": "updated_at",
                "type": "timestamptz",
                "nullable": "NO",
                "pk": "NO",
                "unique": "NO",
                "default": "now()",
                "description": "更新日時",
            },
            {
                "column_name": "disabled_at",
                "type": "timestamptz",
                "nullable": "YES",
                "pk": "NO",
                "unique": "NO",
                "default": "NONE",
                "description": "無効化日時",
            },
        ]
    )
    return rows


def derive_doa(doc: ToonDocument) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "column_name": "id",
            "python_type": "UUID",
            "required": "YES",
            "min": "",
            "max": "",
            "max_length": "",
            "description": "サロゲートキー",
        },
    ]
    for col in doc.columns:
        base, params = _split_type(col.type)
        python_type = _PYTHON_TYPE_MAP.get(base, base)
        max_length = ""
        if base == "varchar" and params:
            max_length = params.strip("()")
        rows.append(
            {
                "column_name": col.physical_name,
                "python_type": python_type,
                "required": "NO" if col.nullable.upper() == "YES" else "YES",
                "min": "",
                "max": "",
                "max_length": max_length,
                "description": col.description,
            }
        )
    rows.extend(
        [
            {
                "column_name": "created_at",
                "python_type": "datetime",
                "required": "YES",
                "min": "",
                "max": "",
                "max_length": "",
                "description": "作成日時",
            },
            {
                "column_name": "updated_at",
                "python_type": "datetime",
                "required": "YES",
                "min": "",
                "max": "",
                "max_length": "",
                "description": "更新日時",
            },
            {
                "column_name": "disabled_at",
                "python_type": "datetime",
                "required": "NO",
                "min": "",
                "max": "",
                "max_length": "",
                "description": "無効化日時",
            },
        ]
    )
    return rows


def derive_all(doc: ToonDocument) -> ToonDocument:
    return doc.model_copy(
        update={
            "logical": derive_logical(doc.columns),
            "physical": derive_physical(doc),
            "doa": derive_doa(doc),
        }
    )


def table_exists(name: str) -> bool:
    return (get_data_dir() / f"{name}.toon").exists()


def list_tables() -> list[TableSummary]:
    index = read_index_toon()
    return index.tables


def get_table(name: str) -> ToonDocument:
    return read_toon(name)


def save_table(name: str, doc: ToonDocument) -> None:
    write_toon(name, doc)
    logger.info("テーブル保存: table=%s", name)


def delete_table(name: str) -> None:
    path = get_data_dir() / f"{name}.toon"
    if not path.exists():
        logger.warning("テーブル削除失敗: table=%s (存在しない)", name)
        raise FileNotFoundError(f"Table '{name}' not found")
    path.unlink()
    logger.info("テーブル削除: table=%s", name)


def generate_er_diagram(tables: list[TableSummary] | None = None) -> str:
    if tables is None:
        index = read_index_toon()
        tables = index.tables
    if not tables:
        return ""
    lines = ["erDiagram"]
    relations: list[str] = []
    for summary in tables:
        display = f'{summary.symbol}["{summary.logical_name}"]'
        lines.append(f"    {display}")
        try:
            doc = read_toon(summary.name)
        except FileNotFoundError:
            continue
        for col in doc.columns:
            if not col.fk_target:
                continue
            target = next((t for t in tables if t.symbol == col.fk_target), None)
            if target is None:
                continue
            nullable = col.nullable.upper() == "YES"
            arrow = "|o--o{" if nullable else "||--o{"
            relations.append(f'    {col.fk_target} {arrow} {summary.symbol} : ""')
    lines.extend(relations)
    return "\n".join(lines)


def rebuild_index() -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    names = sorted(f.stem for f in d.glob("*.toon") if f.stem != "index")
    tables: list[TableSummary] = []
    for name in names:
        try:
            doc = read_toon(name)
        except FileNotFoundError:
            continue
        tables.append(
            TableSummary(
                symbol=doc.meta.symbol or "",
                name=name,
                logical_name=doc.meta.logical_name,
                description=doc.meta.description,
            )
        )
    index = read_index_toon()
    er = generate_er_diagram(tables) if tables else ""
    updated = index.model_copy(update={"tables": tables, "er_diagram": er})
    write_index_toon(updated)
    logger.info("インデックス再構築完了")
