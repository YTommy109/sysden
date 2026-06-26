import re

from app.models import Column, ToonDocument

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

_PHYSICAL_SYSTEM_ROWS: list[dict[str, str]] = [
    {
        "column_name": "id",
        "type": "uuid",
        "nullable": "NO",
        "pk": "YES",
        "unique": "YES",
        "default": "uuidv7()",
        "description": "サロゲートキー",
    },
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

_DAO_SYSTEM_ROWS: list[dict[str, str]] = [
    {
        "column_name": "id",
        "python_type": "UUID",
        "required": "YES",
        "min": "",
        "max": "",
        "max_length": "",
        "description": "サロゲートキー",
    },
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


def _split_type(sql_type: str) -> tuple[str, str]:
    if m := _TYPE_PARAM_RE.match(sql_type):
        return m.group(1).lower(), m.group(2)
    return sql_type.lower(), ""


def derive_logical(columns: list[Column]) -> list[dict[str, str]]:
    """カラム定義から論理設計テーブルを導出する。

    Args:
        columns: カラム定義のリスト。

    Returns:
        論理設計の行データ（カラム名・型・ユニーク・説明）。
    """
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
    """ToonDocument から物理設計テーブルを導出する。

    サロゲートキー (id) とタイムスタンプ列を自動付与する。

    Args:
        doc: 導出元の ToonDocument。

    Returns:
        物理設計の行データ。
    """
    user_rows = [
        {
            "column_name": col.physical_name,
            "type": col.type,
            "nullable": col.nullable,
            "pk": col.pk,
            "unique": col.unique,
            "default": col.default,
            "description": col.description,
        }
        for col in doc.columns
    ]
    return [_PHYSICAL_SYSTEM_ROWS[0], *user_rows, *_PHYSICAL_SYSTEM_ROWS[1:]]


def derive_dao(doc: ToonDocument) -> list[dict[str, str]]:
    """ToonDocument から DAO 定義テーブルを導出する。

    SQL 型を Python 型にマッピングし、サロゲートキーとタイムスタンプ列を自動付与する。

    Args:
        doc: 導出元の ToonDocument。

    Returns:
        DAO 定義の行データ。
    """
    user_rows: list[dict[str, str]] = []
    for col in doc.columns:
        base, params = _split_type(col.type)
        python_type = _PYTHON_TYPE_MAP.get(base, base)
        max_length = params.strip("()") if base == "varchar" and params else ""
        user_rows.append(
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
    return [_DAO_SYSTEM_ROWS[0], *user_rows, *_DAO_SYSTEM_ROWS[1:]]


def derive_all(doc: ToonDocument) -> ToonDocument:
    """論理設計・物理設計・DAO を一括導出して ToonDocument に付与する。

    Args:
        doc: 導出元の ToonDocument。

    Returns:
        logical / physical / dao が設定された ToonDocument。
    """
    return doc.model_copy(
        update={
            "logical": derive_logical(doc.columns),
            "physical": derive_physical(doc),
            "dao": derive_dao(doc),
        }
    )
