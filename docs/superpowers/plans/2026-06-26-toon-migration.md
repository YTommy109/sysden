# TOON フォーマット移行 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TSV + markdown の複数ファイル構成を TOON 単一ファイルに移行し、シンボルベースのテーブル/カラム識別を導入する

**Architecture:** ボトムアップ（データ層 → サービス層 → AI 層 → UI 層）。AI はコア設計のみ生成し、論理/物理/DoA は Python で導出する。1 テーブル = 1 .toon ファイル。

**Tech Stack:** Python 3.14+ / FastAPI / toon-python / OpenAI SDK / Pydantic / htmx + _hyperscript

## Global Constraints

- 行長 100 文字以内（Ruff 強制）
- 認知的複雑度 ≤ 10（C901）
- テストカバレッジ 80% 以上
- テスト関数名は日本語、Arrange/Act/Assert コメントパターン
- コミットメッセージは Conventional Commits + 日本語
- `uv run task lint` と `uv run task typecheck` を各コミット前に通す

---

### Task 1: データモデル + TOON I/O 層

**Files:**
- Create: `app/models.py`
- Create: `app/toon_io.py`
- Create: `tests/unit/test_toon_io.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `app/config.py:get_data_dir()`
- Produces:
  - `app/models.py`: `Column`, `TableMeta`, `ToonDocument`, `TableSummary`, `IndexDocument`
  - `app/toon_io.py`: `read_toon(name: str) -> ToonDocument`, `write_toon(name: str, doc: ToonDocument) -> None`, `read_index_toon() -> IndexDocument`, `write_index_toon(doc: IndexDocument) -> None`, `parse_toon_tables(text: str) -> list[ToonDocument]`

- [ ] **Step 1: toon-python 依存を追加する**

`pyproject.toml` の `dependencies` に `toon-python` を追加する。

```bash
uv add toon-python
```

実行後、`pyproject.toml` の `dependencies` に `toon-python` が追加されていることを確認する。

`uv add` が失敗する場合（パッケージが見つからない等）は、依存追加をスキップして自前パーサーを書く（Step 3 で対応）。

- [ ] **Step 2: テストを書く — models.py**

```python
# tests/unit/test_toon_io.py
import pytest

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
```

- [ ] **Step 3: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_toon_io.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 4: models.py を実装する**

```python
# app/models.py
from pydantic import BaseModel


class Column(BaseModel):
    symbol: str
    logical_name: str
    physical_name: str
    type: str
    nullable: str
    pk: str
    unique: str
    default: str = ""
    fk_target: str = ""
    description: str = ""


class TableMeta(BaseModel):
    symbol: str
    logical_name: str
    physical_name: str
    description: str


class ToonDocument(BaseModel):
    meta: TableMeta
    columns: list[Column]
    logical: list[dict[str, str]] | None = None
    physical: list[dict[str, str]] | None = None
    doa: list[dict[str, str]] | None = None


class TableSummary(BaseModel):
    symbol: str
    name: str
    logical_name: str
    description: str


class IndexDocument(BaseModel):
    description: str
    rules: list[str]
    tables: list[TableSummary]
    er_diagram: str
```

- [ ] **Step 5: モデルテストがパスすることを確認する**

```bash
uv run pytest tests/unit/test_toon_io.py -v
```

Expected: PASS

- [ ] **Step 6: テストを書く — toon_io のパースとシリアライズ**

`tests/unit/test_toon_io.py` に追記する。

```python
from pathlib import Path

from app import toon_io

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
```

- [ ] **Step 7: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_toon_io.py::test_テーブルTOONをパースする -v
```

Expected: FAIL — `AttributeError: module 'app.toon_io' has no attribute 'parse_table_toon'`

- [ ] **Step 8: toon_io.py を実装する**

`toon-python` を使ってパース/シリアライズを行う。もしライブラリの API が合わない場合は以下の自前パーサーを使う。TOON の構文はシンプル（meta=key-value ペア、配列=[N]{fields}: + カンマ区切り行、テキスト=インデント行）なので自前実装でも ~150 行。

```python
# app/toon_io.py
import logging
import re

import yaml

from app.config import get_data_dir
from app.models import Column, IndexDocument, TableMeta, TableSummary, ToonDocument

logger = logging.getLogger(__name__)

_ARRAY_HEADER_RE = re.compile(r"^(\w+)\[(\d+)\]\{(.+)\}:$")
_SECTION_HEADER_RE = re.compile(r"^(\w+):$")
_KV_RE = re.compile(r"^  (\w+):\s*(.*)$")
_INDEX_STEM = "index"

_COLUMNS_FIELDS = [
    "symbol", "logical_name", "physical_name", "type",
    "nullable", "pk", "unique", "default", "fk_target", "description",
]


def _parse_sections(text: str) -> list[tuple[str, str, list[str] | None, list[str]]]:
    sections: list[tuple[str, str, list[str] | None, list[str]]] = []
    current_name: str | None = None
    current_header: str = ""
    current_fields: list[str] | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        array_m = _ARRAY_HEADER_RE.match(line)
        section_m = _SECTION_HEADER_RE.match(line) if not array_m else None

        if array_m or section_m:
            if current_name is not None:
                sections.append(
                    (current_name, current_header, current_fields, current_lines)
                )
            if array_m:
                current_name = array_m.group(1)
                current_header = line
                current_fields = array_m.group(3).split(",")
            else:
                current_name = section_m.group(1)
                current_header = line
                current_fields = None
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        sections.append((current_name, current_header, current_fields, current_lines))

    return sections


def _parse_kv_lines(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        m = _KV_RE.match(line)
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def _parse_array_rows(
    fields: list[str], lines: list[str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        values = stripped.split(",", maxsplit=len(fields) - 1)
        while len(values) < len(fields):
            values.append("")
        rows.append(dict(zip(fields, values)))
    return rows


def _parse_list_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            result.append(stripped[2:])
    return result


def _parse_text_block(lines: list[str]) -> str:
    content_lines: list[str] = []
    for line in lines:
        if line.startswith("  "):
            content_lines.append(line[2:])
        elif line.strip() == "":
            content_lines.append("")
        else:
            content_lines.append(line)
    return "\n".join(content_lines).strip()


def parse_table_toon(text: str) -> ToonDocument:
    sections = _parse_sections(text)
    meta_dict: dict[str, str] = {}
    columns: list[Column] = []
    logical: list[dict[str, str]] | None = None
    physical: list[dict[str, str]] | None = None
    doa: list[dict[str, str]] | None = None

    for name, _header, fields, lines in sections:
        if name == "meta":
            meta_dict = _parse_kv_lines(lines)
        elif name == "columns" and fields:
            columns = [Column(**row) for row in _parse_array_rows(fields, lines)]
        elif name == "logical" and fields:
            logical = _parse_array_rows(fields, lines)
        elif name == "physical" and fields:
            physical = _parse_array_rows(fields, lines)
        elif name == "doa" and fields:
            doa = _parse_array_rows(fields, lines)

    meta = TableMeta(**meta_dict)
    return ToonDocument(
        meta=meta, columns=columns, logical=logical,
        physical=physical, doa=doa,
    )


def parse_index_toon(text: str) -> IndexDocument:
    sections = _parse_sections(text)
    description = ""
    rules: list[str] = []
    tables: list[TableSummary] = []
    er_diagram = ""

    for name, _header, fields, lines in sections:
        if name == "meta":
            kv = _parse_kv_lines(lines)
            description = kv.get("description", "")
        elif name == "rules":
            rules = _parse_list_lines(lines)
        elif name == "tables" and fields:
            tables = [
                TableSummary(**row) for row in _parse_array_rows(fields, lines)
            ]
        elif name == "er_diagram":
            er_diagram = _parse_text_block(lines)

    return IndexDocument(
        description=description, rules=rules,
        tables=tables, er_diagram=er_diagram,
    )


def parse_toon_tables(text: str) -> list[ToonDocument]:
    chunks: list[str] = []
    current_lines: list[str] = []
    seen_meta = False

    for line in text.splitlines():
        if line.strip() == "meta:" and seen_meta:
            chunks.append("\n".join(current_lines))
            current_lines = []
        if line.strip() == "meta:":
            seen_meta = True
        current_lines.append(line)

    if current_lines:
        chunks.append("\n".join(current_lines))

    return [parse_table_toon(chunk) for chunk in chunks]


def _serialize_array_section(
    name: str, fields: list[str], rows: list[dict[str, str]]
) -> str:
    header = f"{name}[{len(rows)}]{{{','.join(fields)}}}:"
    lines = [header]
    for row in rows:
        values = [row.get(f, "") for f in fields]
        lines.append(f"  {','.join(values)}")
    return "\n".join(lines)


def serialize_table_toon(doc: ToonDocument) -> str:
    parts: list[str] = []

    parts.append("meta:")
    parts.append(f"  symbol: {doc.meta.symbol}")
    parts.append(f"  logical_name: {doc.meta.logical_name}")
    parts.append(f"  physical_name: {doc.meta.physical_name}")
    parts.append(f"  description: {doc.meta.description}")

    col_dicts = [col.model_dump() for col in doc.columns]
    parts.append("")
    parts.append(_serialize_array_section("columns", _COLUMNS_FIELDS, col_dicts))

    if doc.logical is not None:
        fields = list(doc.logical[0].keys()) if doc.logical else []
        parts.append("")
        parts.append(_serialize_array_section("logical", fields, doc.logical))

    if doc.physical is not None:
        fields = list(doc.physical[0].keys()) if doc.physical else []
        parts.append("")
        parts.append(_serialize_array_section("physical", fields, doc.physical))

    if doc.doa is not None:
        fields = list(doc.doa[0].keys()) if doc.doa else []
        parts.append("")
        parts.append(_serialize_array_section("doa", fields, doc.doa))

    return "\n".join(parts) + "\n"


def serialize_index_toon(index: IndexDocument) -> str:
    parts: list[str] = []

    parts.append("meta:")
    parts.append(f"  description: {index.description}")

    parts.append("")
    parts.append("rules:")
    for rule in index.rules:
        parts.append(f"  - {rule}")

    if index.tables:
        table_fields = ["symbol", "name", "logical_name", "description"]
        table_dicts = [t.model_dump() for t in index.tables]
        parts.append("")
        parts.append(
            _serialize_array_section("tables", table_fields, table_dicts)
        )

    if index.er_diagram:
        parts.append("")
        parts.append("er_diagram:")
        for line in index.er_diagram.splitlines():
            parts.append(f"  {line}")

    return "\n".join(parts) + "\n"


def read_toon(name: str) -> ToonDocument:
    path = get_data_dir() / f"{name}.toon"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    text = path.read_text(encoding="utf-8")
    return parse_table_toon(text)


def write_toon(name: str, doc: ToonDocument) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.toon"
    path.write_text(serialize_table_toon(doc), encoding="utf-8")
    logger.info("TOON 書き込み: table=%s", name)


def read_index_toon() -> IndexDocument:
    path = get_data_dir() / f"{_INDEX_STEM}.toon"
    if not path.exists():
        return IndexDocument(
            description="テーブル設計インデックス",
            rules=[], tables=[], er_diagram="",
        )
    text = path.read_text(encoding="utf-8")
    return parse_index_toon(text)


def write_index_toon(doc: IndexDocument) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_INDEX_STEM}.toon"
    path.write_text(serialize_index_toon(doc), encoding="utf-8")
    logger.info("インデックス TOON 書き込み")
```

- [ ] **Step 9: テストを書く — ファイル読み書き**

`tests/unit/test_toon_io.py` に追記する。

```python
def test_TOONファイルの書き込みと読み込み() -> None:
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
    doc = ToonDocument(meta=meta, columns=[col])

    # Act
    toon_io.write_toon("users", doc)
    loaded = toon_io.read_toon("users")

    # Assert
    assert loaded.meta.symbol == "TABLE_0001"
    assert loaded.columns[0].physical_name == "id"


def test_存在しないTOONの読み込みはFileNotFoundError() -> None:
    # Act & Assert
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        toon_io.read_toon("nonexistent")


def test_インデックスTOONファイルが存在しなければデフォルトを返す() -> None:
    # Act
    index = toon_io.read_index_toon()

    # Assert
    assert index.tables == []
    assert index.rules == []
    assert index.er_diagram == ""


def test_インデックスTOONの書き込みと読み込み() -> None:
    # Arrange
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
```

- [ ] **Step 10: 全テストがパスすることを確認する**

```bash
uv run pytest tests/unit/test_toon_io.py -v
```

Expected: ALL PASS

- [ ] **Step 11: lint + typecheck**

```bash
uv run task lint && uv run task typecheck
```

Expected: PASS（警告があれば修正）

- [ ] **Step 12: コミット**

```bash
git add app/models.py app/toon_io.py tests/unit/test_toon_io.py pyproject.toml uv.lock
git commit -m "feat: TOON I/O 層とデータモデルを追加する

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: シンボルサービス

**Files:**
- Create: `app/symbol_service.py`
- Create: `tests/unit/test_symbol_service.py`

**Interfaces:**
- Consumes: `app/config.py:get_data_dir()`, `app/models.py:ToonDocument`, `app/models.py:Column`, `app/models.py:TableMeta`
- Produces:
  - `allocate_table_symbol() -> str`
  - `allocate_column_symbols(count: int) -> list[str]`
  - `remap_placeholders(designs: list[ToonDocument], symbol_map: dict[str, str]) -> list[ToonDocument]`

- [ ] **Step 1: テストを書く**

```python
# tests/unit/test_symbol_service.py
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


def test_最初のテーブルシンボルはTABLE_0001(tmp_path: Path) -> None:
    # Arrange — index.yaml が存在しない

    # Act
    symbol = symbol_service.allocate_table_symbol()

    # Assert
    assert symbol == "TABLE_0001"


def test_連続で採番すると連番になる() -> None:
    # Arrange — 1 回目の採番
    s1 = symbol_service.allocate_table_symbol()

    # Act — 2 回目の採番
    s2 = symbol_service.allocate_table_symbol()

    # Assert
    assert s1 == "TABLE_0001"
    assert s2 == "TABLE_0002"


def test_既存のindex_yamlから採番を継続する(tmp_path: Path) -> None:
    # Arrange — next_table_id: 5 の index.yaml を用意
    (tmp_path / "index.yaml").write_text(
        yaml.dump({"next_table_id": 5}), encoding="utf-8"
    )

    # Act
    symbol = symbol_service.allocate_table_symbol()

    # Assert
    assert symbol == "TABLE_0005"

    # Assert — index.yaml が更新されている
    data = yaml.safe_load((tmp_path / "index.yaml").read_text(encoding="utf-8"))
    assert data["next_table_id"] == 6


def test_カラムシンボルを生成する() -> None:
    # Act
    symbols = symbol_service.allocate_column_symbols(3)

    # Assert
    assert symbols == ["COLUMN_0001", "COLUMN_0002", "COLUMN_0003"]


def test_カラムシンボル0個は空リスト() -> None:
    # Act
    symbols = symbol_service.allocate_column_symbols(0)

    # Assert
    assert symbols == []


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
    result = symbol_service.remap_placeholders(
        [doc], {}, table_symbols=["TABLE_0010"]
    )

    # Assert
    assert result[0].meta.symbol == "TABLE_0010"
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_symbol_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.symbol_service'`

- [ ] **Step 3: symbol_service.py を実装する**

```python
# app/symbol_service.py
import logging

import yaml

from app.config import get_data_dir
from app.models import Column, ToonDocument

logger = logging.getLogger(__name__)

_INDEX_YAML = "index.yaml"


def _read_next_id() -> int:
    path = get_data_dir() / _INDEX_YAML
    if not path.exists():
        return 1
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return int(data.get("next_table_id", 1))


def _write_next_id(next_id: int) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / _INDEX_YAML
    path.write_text(
        yaml.dump({"next_table_id": next_id}), encoding="utf-8"
    )


def allocate_table_symbol() -> str:
    next_id = _read_next_id()
    symbol = f"TABLE_{next_id:04d}"
    _write_next_id(next_id + 1)
    logger.info("テーブルシンボル採番: %s", symbol)
    return symbol


def allocate_column_symbols(count: int) -> list[str]:
    return [f"COLUMN_{i:04d}" for i in range(1, count + 1)]


def remap_placeholders(
    designs: list[ToonDocument],
    symbol_map: dict[str, str],
    *,
    table_symbols: list[str] | None = None,
) -> list[ToonDocument]:
    result: list[ToonDocument] = []
    for i, doc in enumerate(designs):
        meta = doc.meta
        if table_symbols and i < len(table_symbols):
            meta = meta.model_copy(update={"symbol": table_symbols[i]})

        new_columns: list[Column] = []
        for col in doc.columns:
            if col.fk_target in symbol_map:
                col = col.model_copy(
                    update={"fk_target": symbol_map[col.fk_target]}
                )
            new_columns.append(col)

        result.append(doc.model_copy(
            update={"meta": meta, "columns": new_columns}
        ))
    return result
```

- [ ] **Step 4: テストがパスすることを確認する**

```bash
uv run pytest tests/unit/test_symbol_service.py -v
```

Expected: ALL PASS

- [ ] **Step 5: lint + typecheck**

```bash
uv run task lint && uv run task typecheck
```

- [ ] **Step 6: コミット**

```bash
git add app/symbol_service.py tests/unit/test_symbol_service.py
git commit -m "feat: シンボル採番・リマップサービスを追加する

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: テーブルサービス（導出 + CRUD + ER 図 + インデックス）

**Files:**
- Rewrite: `app/table_service.py`
- Rewrite: `tests/unit/test_table_service.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes:
  - `app/toon_io.py`: `read_toon`, `write_toon`, `read_index_toon`, `write_index_toon`, `parse_table_toon`
  - `app/models.py`: `Column`, `ToonDocument`, `TableMeta`, `TableSummary`, `IndexDocument`
- Produces:
  - `validate_table_name(name: str) -> bool`
  - `list_tables() -> list[TableSummary]`
  - `get_table(name: str) -> ToonDocument`
  - `save_table(name: str, doc: ToonDocument) -> None`
  - `delete_table(name: str) -> None`
  - `table_exists(name: str) -> bool`
  - `derive_logical(columns: list[Column]) -> list[dict[str, str]]`
  - `derive_physical(columns: list[Column]) -> list[dict[str, str]]`
  - `derive_doa(columns: list[Column]) -> list[dict[str, str]]`
  - `derive_all(doc: ToonDocument) -> ToonDocument`
  - `generate_er_diagram() -> str`
  - `rebuild_index() -> None`

- [ ] **Step 1: conftest.py を更新する**

`tests/conftest.py` を以下に書き換える。

```python
# tests/conftest.py
from pathlib import Path
from types import SimpleNamespace

import pytest

SAMPLE_TOON = """\
meta:
  symbol: TABLE_0001
  logical_name: ユーザー
  physical_name: users
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,,,主キー
"""

SAMPLE_CORE_TOON = """\
meta:
  logical_name: スタブ
  physical_name: stub_table
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー
"""


def make_fake_openai_client(
    response: str = SAMPLE_CORE_TOON,
    calls: list[dict] | None = None,
) -> SimpleNamespace:
    """OpenAI API 構造を模倣するスタブクライアントを生成する。"""

    def create(**kwargs: object) -> SimpleNamespace:
        if calls is not None:
            calls.append(kwargs)
        choice = SimpleNamespace(message=SimpleNamespace(content=response))
        return SimpleNamespace(choices=[choice])

    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


@pytest.fixture()
def sample_toon() -> str:
    """テスト用の最小限テーブル TOON。"""
    return SAMPLE_TOON


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """全テストで一時データディレクトリと API キーを設定する。"""
    monkeypatch.setenv("SYSDEN_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
```

- [ ] **Step 2: 導出ロジックのテストを書く**

```python
# tests/unit/test_table_service.py
import logging
import re

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
def test_DoAでSQL型がPython型に変換される(
    sql_type: str, expected_python_type: str
) -> None:
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
```

- [ ] **Step 3: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_table_service.py::test_論理設計で日本語カラム名が使われる -v
```

Expected: FAIL

- [ ] **Step 4: table_service.py を書き換える — 導出ロジック**

`app/table_service.py` を完全に書き換える。

```python
# app/table_service.py
import logging
import re

from app.config import get_data_dir
from app.models import Column, IndexDocument, TableSummary, ToonDocument
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
    "timestamp": "タイムスタンプ",
    "timestamptz": "タイムスタンプ",
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
        rows.append({
            "カラム名": col.logical_name,
            "型": jp_type,
            "ユニーク": "○" if col.unique.upper() == "YES" else "",
            "説明": col.description,
        })
    return rows


def derive_physical(columns: list[Column]) -> list[dict[str, str]]:
    return [
        {
            "column_name": col.physical_name,
            "type": col.type,
            "nullable": col.nullable,
            "pk": col.pk,
            "unique": col.unique,
            "default": col.default,
            "description": col.description,
        }
        for col in columns
    ]


def derive_doa(columns: list[Column]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for col in columns:
        base, params = _split_type(col.type)
        python_type = _PYTHON_TYPE_MAP.get(base, base)
        max_length = ""
        if base == "varchar" and params:
            max_length = params.strip("()")
        rows.append({
            "column_name": col.physical_name,
            "python_type": python_type,
            "required": "NO" if col.nullable.upper() == "YES" else "YES",
            "min": "",
            "max": "",
            "max_length": max_length,
            "description": col.description,
        })
    return rows


def derive_all(doc: ToonDocument) -> ToonDocument:
    return doc.model_copy(update={
        "logical": derive_logical(doc.columns),
        "physical": derive_physical(doc.columns),
        "doa": derive_doa(doc.columns),
    })


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


def generate_er_diagram() -> str:
    index = read_index_toon()
    if not index.tables:
        return ""
    lines = ["erDiagram"]
    relations: list[str] = []
    for summary in index.tables:
        display = f'{summary.symbol}["{summary.logical_name}"]'
        lines.append(f"    {display}")
        try:
            doc = read_toon(summary.name)
        except FileNotFoundError:
            continue
        for col in doc.columns:
            if not col.fk_target:
                continue
            target = next(
                (t for t in index.tables if t.symbol == col.fk_target), None
            )
            if target is None:
                continue
            nullable = col.nullable.upper() == "YES"
            arrow = "|o--o{" if nullable else "||--o{"
            relations.append(
                f'    {col.fk_target} {arrow} {summary.symbol} : ""'
            )
    lines.extend(relations)
    return "\n".join(lines)


def rebuild_index() -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    names = sorted(
        f.stem for f in d.glob("*.toon") if f.stem != "index"
    )
    tables: list[TableSummary] = []
    for name in names:
        try:
            doc = read_toon(name)
        except FileNotFoundError:
            continue
        tables.append(TableSummary(
            symbol=doc.meta.symbol,
            name=name,
            logical_name=doc.meta.logical_name,
            description=doc.meta.description,
        ))
    index = read_index_toon()
    er = generate_er_diagram() if tables else ""
    updated = index.model_copy(update={"tables": tables, "er_diagram": er})
    write_index_toon(updated)
    logger.info("インデックス再構築完了")
```

- [ ] **Step 5: CRUD + ER 図 + インデックスのテストを書く**

`tests/unit/test_table_service.py` に追記する。

```python
from app import toon_io


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
    from app.models import Column, TableMeta, ToonDocument

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
    from app.models import TableMeta

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
    def test_テーブル保存時にログ出力される(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        doc = parse_table_toon(SAMPLE_TOON)
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.save_table("users", doc)
        assert "テーブル保存: table=users" in caplog.text

    def test_テーブル削除時にログ出力される(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        doc = parse_table_toon(SAMPLE_TOON)
        table_service.save_table("users", doc)
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.delete_table("users")
        assert "テーブル削除: table=users" in caplog.text

    def test_インデックス再構築完了がログ出力される(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="app.table_service"):
            table_service.rebuild_index()
        assert "インデックス再構築完了" in caplog.text
```

- [ ] **Step 6: 全テストがパスすることを確認する**

```bash
uv run pytest tests/unit/test_table_service.py -v
```

Expected: ALL PASS

- [ ] **Step 7: lint + typecheck**

```bash
uv run task lint && uv run task typecheck
```

- [ ] **Step 8: コミット**

```bash
git add app/table_service.py tests/unit/test_table_service.py tests/conftest.py
git commit -m "feat: テーブルサービスを TOON ベースに書き換える

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: AI サービス書き換え

**Files:**
- Rewrite: `prompts/ai_prompts.yaml`
- Rewrite: `app/ai_service.py`
- Rewrite: `tests/unit/test_ai_service.py`

**Interfaces:**
- Consumes:
  - `app/toon_io.py`: `parse_toon_tables`, `parse_table_toon`
  - `app/models.py`: `ToonDocument`, `TableSummary`, `Column`
- Produces:
  - `create_table_design(prompt: str, rules: list[str], existing_tables: list[TableSummary]) -> list[ToonDocument]`
  - `update_table_design(prompt: str, current: ToonDocument, rules: list[str], existing_tables: list[TableSummary]) -> ToonDocument`
  - `get_client() -> OpenAI`

- [ ] **Step 1: ai_prompts.yaml を書き換える**

```yaml
# prompts/ai_prompts.yaml
core_create:
  system: |
    あなたはデータベーステーブル設計のアシスタントです。
    ユーザーの依頼に応じて、TOON フォーマットでテーブルのコア設計を出力してください。

    出力フォーマット（テーブルごとに meta + columns を出力）:
    meta:
      logical_name: 日本語テーブル名
      physical_name: 英語スネークケース
      description: テーブルの説明

    columns[N]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
      COLUMN_0001,日本語カラム名,英語カラム名,SQL型,YES/NO,YES/NO,YES/NO,デフォルト値,FK参照先シンボル,説明
      ...

    出力規則:
    - symbol は COLUMN_0001 から連番で付与する
    - type は具体的な SQL 型（uuid, varchar(255), integer, decimal(10,2), timestamptz など）
    - nullable, pk, unique は YES または NO
    - fk_target は参照先テーブルのシンボル。既存テーブルは提供されたシンボルを使用する
    - 同一リクエスト内の新規テーブルを参照する場合は NEW_1, NEW_2 等のプレースホルダを使用する
    - 共通ルールで指定されたカラムを必ず含めること
    - [N] はデータ行数と一致させること
    - description はカラム名から自明でない補足情報がある場合のみ記載する
    - 複数テーブルを出力する場合、テーブル間は空行で区切る
    - コードブロック記号（```）は不要

  user_template: |
    共通ルール:
    {rules}

    既存テーブル:
    {existing_tables}

    依頼: {prompt}

  model: gpt-4o
  temperature: 0.2

core_update:
  system: |
    あなたはデータベーステーブル設計のアシスタントです。
    既存のコア設計を更新してください。出力は更新後のコア設計全体を TOON フォーマットで返してください。

    出力フォーマット:
    meta:
      logical_name: 日本語テーブル名
      physical_name: 英語スネークケース
      description: テーブルの説明

    columns[N]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
      COLUMN_0001,...
      ...

    出力規則:
    - 既存カラムの symbol は変更しない
    - 新規カラムには既存の最大番号の次の番号を付与する
    - type は具体的な SQL 型（uuid, varchar(255), integer, decimal(10,2), timestamptz など）
    - nullable, pk, unique は YES または NO
    - fk_target は参照先テーブルのシンボルを使用する
    - 共通ルールで指定されたカラムを必ず含めること
    - [N] はデータ行数と一致させること
    - コードブロック記号（```）は不要

  user_template: |
    現在のコア設計:
    {current_core}

    共通ルール:
    {rules}

    既存テーブル:
    {existing_tables}

    依頼: {prompt}

  model: gpt-4o
  temperature: 0.2
```

- [ ] **Step 2: テストを書く**

```python
# tests/unit/test_ai_service.py
import logging

import pytest

from app import ai_service
from app.models import TableSummary, ToonDocument
from app.toon_io import serialize_table_toon
from tests.conftest import SAMPLE_CORE_TOON, make_fake_openai_client

MULTI_TABLE_RESPONSE = """\
meta:
  logical_name: ユーザー
  physical_name: users
  description: ユーザー情報

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,

meta:
  logical_name: 注文
  physical_name: orders
  description: 注文情報

columns[2]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,注文ID,order_id,uuid,NO,YES,YES,gen_random_uuid(),,
  COLUMN_0002,注文者,user_id,uuid,NO,NO,NO,,NEW_1,
"""

SINGLE_TABLE_RESPONSE = SAMPLE_CORE_TOON


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """OpenAI クライアントをスタブに差し替え、API 呼び出しを記録する。"""
    calls: list[dict] = []
    monkeypatch.setattr(
        ai_service, "get_client", lambda: make_fake_openai_client(calls=calls)
    )
    return calls


def test_単一テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=SINGLE_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design(
        prompt="テストテーブルを作って", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 1
    assert tables[0].meta.physical_name == "stub_table"
    assert len(tables[0].columns) == 1


def test_複数テーブルの生成(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=MULTI_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)

    # Act
    tables = ai_service.create_table_design(
        prompt="ユーザーと注文テーブルを作って", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 2
    assert tables[0].meta.physical_name == "users"
    assert tables[1].meta.physical_name == "orders"
    assert tables[1].columns[1].fk_target == "NEW_1"


def test_テーブル更新(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake = make_fake_openai_client(response=SINGLE_TABLE_RESPONSE)
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)
    from app.toon_io import parse_table_toon

    current = parse_table_toon(SINGLE_TABLE_RESPONSE)

    # Act
    result = ai_service.update_table_design(
        prompt="カラムを追加",
        current=current,
        rules=[],
        existing_tables=[],
    )

    # Assert
    assert isinstance(result, ToonDocument)
    assert result.meta.physical_name == "stub_table"


def test_更新モードで現在のコア設計がプロンプトに含まれる(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    calls: list[dict] = []
    fake = make_fake_openai_client(
        response=SINGLE_TABLE_RESPONSE, calls=calls
    )
    monkeypatch.setattr(ai_service, "get_client", lambda: fake)
    from app.toon_io import parse_table_toon

    current = parse_table_toon(SINGLE_TABLE_RESPONSE)

    # Act
    ai_service.update_table_design(
        prompt="カラムを追加",
        current=current,
        rules=["ルール1"],
        existing_tables=[
            TableSummary(
                symbol="TABLE_0001",
                name="test",
                logical_name="テスト",
                description="",
            )
        ],
    )

    # Assert
    msgs = calls[0]["messages"]
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert "現在のコア設計" in user_msg["content"]
    assert "ルール1" in user_msg["content"]
    assert "TABLE_0001" in user_msg["content"]


def test_テストモードでスタブを返す(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")

    # Act
    tables = ai_service.create_table_design(
        prompt="何でも", rules=[], existing_tables=[]
    )

    # Assert
    assert len(tables) == 1
    assert tables[0].meta.physical_name == "stub_table"
    assert len(tables[0].columns) >= 1


def test_APIキー未設定でValueError(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Act & Assert
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        ai_service.get_client()


class TestAiServiceLogging:
    def test_生成開始と完了がログ出力される(
        self, mock_openai: list[dict], caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.create_table_design(
                prompt="テスト", rules=[], existing_tables=[]
            )
        assert "AI コア設計生成開始" in caplog.text
        assert "AI コア設計生成完了" in caplog.text

    def test_テストモードのログ出力(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("SYSDEN_TEST_MODE", "1")
        with caplog.at_level(logging.INFO, logger="app.ai_service"):
            ai_service.create_table_design(
                prompt="テスト", rules=[], existing_tables=[]
            )
        assert "テストモード" in caplog.text
```

- [ ] **Step 3: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_ai_service.py::test_単一テーブルの生成 -v
```

Expected: FAIL

- [ ] **Step 4: ai_service.py を書き換える**

```python
# app/ai_service.py
import logging
import os
from pathlib import Path

import yaml
from openai import OpenAI

from app.models import TableSummary, ToonDocument
from app.toon_io import parse_table_toon, parse_toon_tables, serialize_table_toon

logger = logging.getLogger(__name__)

_STUB_CORE_TOON = """\
meta:
  logical_name: スタブ
  physical_name: stub_table
  description: テスト用テーブル

columns[1]{symbol,logical_name,physical_name,type,nullable,pk,unique,default,fk_target,description}:
  COLUMN_0001,識別子,id,uuid,NO,YES,YES,gen_random_uuid(),,主キー
"""

_PROMPTS_PATH = Path(__file__).parent.parent / "prompts" / "ai_prompts.yaml"


def _load_prompts() -> dict:
    with _PROMPTS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY が設定されていません")
    return OpenAI(api_key=api_key)


def _format_existing_tables(tables: list[TableSummary]) -> str:
    if not tables:
        return "なし"
    lines: list[str] = []
    for t in tables:
        lines.append(f"{t.symbol}: {t.logical_name} ({t.name})")
    return "\n".join(lines)


def create_table_design(
    prompt: str,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> list[ToonDocument]:
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計生成スキップ (テストモード)")
        return [parse_table_toon(_STUB_CORE_TOON)]

    logger.info("AI コア設計生成開始: prompt_length=%d", len(prompt))
    config = _load_prompts()["core_create"]
    user_message = config["user_template"].format(
        rules="\n".join(f"- {r}" for r in rules) if rules else "なし",
        existing_tables=_format_existing_tables(existing_tables),
        prompt=prompt,
    )

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": config["system"]},
                {"role": "user", "content": user_message},
            ],
            temperature=config["temperature"],
        )
    except Exception:
        logger.exception("AI コア設計生成失敗")
        raise
    content = response.choices[0].message.content or ""
    tables = parse_toon_tables(content)
    logger.info("AI コア設計生成完了: tables=%d", len(tables))
    return tables


def update_table_design(
    prompt: str,
    current: ToonDocument,
    rules: list[str],
    existing_tables: list[TableSummary],
) -> ToonDocument:
    if os.environ.get("SYSDEN_TEST_MODE") == "1":
        logger.info("AI コア設計更新スキップ (テストモード)")
        return parse_table_toon(_STUB_CORE_TOON)

    logger.info("AI コア設計更新開始: table=%s", current.meta.physical_name)
    config = _load_prompts()["core_update"]
    user_message = config["user_template"].format(
        current_core=serialize_table_toon(current),
        rules="\n".join(f"- {r}" for r in rules) if rules else "なし",
        existing_tables=_format_existing_tables(existing_tables),
        prompt=prompt,
    )

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": config["system"]},
                {"role": "user", "content": user_message},
            ],
            temperature=config["temperature"],
        )
    except Exception:
        logger.exception("AI コア設計更新失敗: table=%s", current.meta.physical_name)
        raise
    content = response.choices[0].message.content or ""
    result = parse_table_toon(content)
    logger.info("AI コア設計更新完了: table=%s", current.meta.physical_name)
    return result
```

- [ ] **Step 5: テストがパスすることを確認する**

```bash
uv run pytest tests/unit/test_ai_service.py -v
```

Expected: ALL PASS

- [ ] **Step 6: lint + typecheck**

```bash
uv run task lint && uv run task typecheck
```

- [ ] **Step 7: コミット**

```bash
git add app/ai_service.py prompts/ai_prompts.yaml tests/unit/test_ai_service.py
git commit -m "feat: AI サービスを TOON コア設計ベースに書き換える

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: ルーター + テンプレート + クリーンアップ

**Files:**
- Modify: `app/routers/html.py`
- Modify: `app/routers/api.py`
- Rewrite: `templates/table_detail.html`
- Modify: `templates/index.html`
- Delete: `templates/physical_detail.html`
- Rewrite: `tests/integration/test_routes.py`
- Modify: `tests/e2e/test_physical_design_page.py` (削除)
- Modify: `tests/e2e/test_table_detail_page.py` (更新)
- Modify: `tests/e2e/test_navigation.py` (更新)

**Interfaces:**
- Consumes:
  - `app/table_service.py`: `list_tables`, `get_table`, `save_table`, `delete_table`, `table_exists`, `validate_table_name`, `derive_all`, `rebuild_index`
  - `app/ai_service.py`: `create_table_design`, `update_table_design`
  - `app/symbol_service.py`: `allocate_table_symbol`, `remap_placeholders`
  - `app/toon_io.py`: `read_index_toon`
  - `app/models.py`: `ToonDocument`, `TableSummary`

- [ ] **Step 1: html.py を書き換える**

```python
# app/routers/html.py
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from app import table_service
from app.toon_io import read_index_toon

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "templates")
)
_md = MarkdownIt("commonmark", {"html": True}).enable("table")


def _dict_list_to_markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_（データなし）_"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(row.get(h, "")) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    index_doc = read_index_toon()
    tables = [
        {"name": t.name, "display_name": t.logical_name}
        for t in index_doc.tables
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tables": tables, "er_diagram": index_doc.er_diagram},
    )


@router.get("/tables/{name}", response_class=HTMLResponse)
def table_detail(name: str, request: Request) -> HTMLResponse:
    if not table_service.validate_table_name(name):
        raise HTTPException(status_code=422, detail=f"Invalid table name: '{name}'")
    try:
        doc = table_service.get_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    logical_html = ""
    physical_html = ""
    doa_html = ""

    if doc.logical:
        logical_html = _md.render(_dict_list_to_markdown_table(doc.logical))
    if doc.physical:
        physical_html = _md.render(_dict_list_to_markdown_table(doc.physical))
    if doc.doa:
        doa_html = _md.render(_dict_list_to_markdown_table(doc.doa))

    return templates.TemplateResponse(
        request,
        "table_detail.html",
        {
            "name": name,
            "display_name": doc.meta.logical_name,
            "symbol": doc.meta.symbol,
            "logical_html": logical_html,
            "physical_html": physical_html,
            "doa_html": doa_html,
        },
    )
```

- [ ] **Step 2: api.py を書き換える**

```python
# app/routers/api.py
import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from app import ai_service, symbol_service, table_service
from app.toon_io import read_index_toon

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _check_table_name(name: str) -> None:
    if not table_service.validate_table_name(name):
        raise HTTPException(
            status_code=422, detail=f"Invalid table name: '{name}'"
        )


def _rebuilding_response(
    sse_url: str, target: str, label: str
) -> HTMLResponse:
    return HTMLResponse(
        f'<div sse-connect="{sse_url}"'
        f' hx-trigger="sse:complete" hx-get="/"'
        f' hx-select="{target}" hx-target="{target}" hx-swap="outerHTML"'
        f' style="margin:0;">'
        f'<button type="button" disabled aria-label="{label}" title="{label}"'
        f' style="background:#555; padding:0.3rem 0.45rem; line-height:0;">'
        f'<img src="/static/icons/arrow-path.svg" alt=""'
        f' style="width:1.1rem; height:1.1rem;" class="spinning">'
        f"</button></div>"
    )


@router.post("/tables")
def create_table(
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    logger.info("テーブル作成リクエスト: prompt_length=%d", len(prompt))
    index = read_index_toon()
    designs = ai_service.create_table_design(
        prompt=prompt,
        rules=index.rules,
        existing_tables=index.tables,
    )

    for doc in designs:
        _check_table_name(doc.meta.physical_name)
        if table_service.table_exists(doc.meta.physical_name):
            raise HTTPException(
                status_code=409,
                detail=f"Table '{doc.meta.physical_name}' already exists",
            )

    table_symbols = [
        symbol_service.allocate_table_symbol() for _ in designs
    ]
    placeholder_map: dict[str, str] = {}
    for i, doc in enumerate(designs):
        placeholder = f"NEW_{i + 1}"
        placeholder_map[placeholder] = table_symbols[i]
    designs = symbol_service.remap_placeholders(
        designs, placeholder_map, table_symbols=table_symbols
    )

    written: list[str] = []
    try:
        for doc in designs:
            doc = table_service.derive_all(doc)
            name = doc.meta.physical_name
            table_service.save_table(name, doc)
            written.append(name)
    except Exception:
        for name in written:
            table_service.delete_table(name)
        raise
    table_service.rebuild_index()
    logger.info(
        "テーブル作成完了: tables=%s",
        [d.meta.physical_name for d in designs],
    )
    redirect_url = (
        f"/tables/{designs[0].meta.physical_name}"
        if len(designs) == 1
        else "/"
    )
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    request: Request,
    prompt: Annotated[str, Form()],
) -> Response:
    logger.info("テーブル更新リクエスト: table=%s", name)
    _check_table_name(name)
    try:
        current = table_service.get_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    index = read_index_toon()
    updated = ai_service.update_table_design(
        prompt=prompt,
        current=current,
        rules=index.rules,
        existing_tables=index.tables,
    )
    updated = updated.model_copy(
        update={"meta": updated.meta.model_copy(
            update={"symbol": current.meta.symbol}
        )}
    )
    updated = table_service.derive_all(updated)
    table_service.save_table(name, updated)
    table_service.rebuild_index()
    logger.info("テーブル更新完了: table=%s", name)
    redirect_url = f"/tables/{name}"
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": redirect_url})
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/rebuild-index-tables")
def rebuild_index_tables(request: Request) -> Response:
    if request.headers.get("HX-Request"):
        return _rebuilding_response(
            "/api/sse/rebuild-index", "#index-body", "テーブル一覧の再作成"
        )
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.post("/rebuild-er-diagram")
def rebuild_er_diagram(request: Request) -> Response:
    if request.headers.get("HX-Request"):
        return _rebuilding_response(
            "/api/sse/rebuild-er", "#er-diagram", "ER 図の再作成"
        )
    table_service.rebuild_index()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    _check_table_name(name)
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    table_service.rebuild_index()
    logger.info("テーブル削除完了: table=%s", name)
    return {"status": "deleted", "name": name}


_MIN_SPIN_SECONDS = 0.5


async def _sse_rebuild(func: Callable[[], object]) -> StreamingResponse:
    async def generate():
        t0 = asyncio.get_event_loop().time()
        try:
            await asyncio.to_thread(func)
        except Exception:
            logger.exception("%s failed", getattr(func, "__name__", func))
        elapsed = asyncio.get_event_loop().time() - t0
        remaining = _MIN_SPIN_SECONDS - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        yield "event: complete\ndata: done\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/sse/rebuild-index")
async def sse_rebuild_index() -> StreamingResponse:
    return await _sse_rebuild(table_service.rebuild_index)


@router.get("/sse/rebuild-er")
async def sse_rebuild_er() -> StreamingResponse:
    return await _sse_rebuild(table_service.rebuild_index)
```

- [ ] **Step 3: table_detail.html を書き換える**

```html
{% extends "base.html" %}
{% block title %}{{ display_name }} — sysden{% endblock %}
{% block content %}
<a href="/">&larr; 一覧</a>
<h1>{{ display_name }}</h1>
<p style="color:#888;">{{ symbol }}</p>

<div class="tabs">
  <button class="tab active"
    _="on click add .active to me remove .active from .tab in .tabs then show #logical hide #physical hide #doa">論理設計</button>
  <button class="tab"
    _="on click add .active to me remove .active from .tab in .tabs then hide #logical show #physical hide #doa">物理設計</button>
  <button class="tab"
    _="on click add .active to me remove .active from .tab in .tabs then hide #logical hide #physical show #doa">DoA</button>
</div>

<div id="logical">{{ logical_html | safe }}</div>
<div id="physical" style="display:none;">{{ physical_html | safe }}</div>
<div id="doa" style="display:none;">{{ doa_html | safe }}</div>

<form method="post" action="/api/tables/{{ name }}"
  hx-post="/api/tables/{{ name }}">
  <textarea name="prompt" required placeholder="更新依頼を入力..."></textarea>
  <button type="submit">送信</button>
</form>
{% endblock %}
```

- [ ] **Step 4: physical_detail.html を削除する**

```bash
git rm templates/physical_detail.html
```

- [ ] **Step 5: integration テストを書き換える**

`tests/integration/test_routes.py` を以下に書き換える。

```python
# tests/integration/test_routes.py
import pytest
from fastapi.testclient import TestClient

from app import table_service
from app.models import Column, TableMeta, ToonDocument
from app.toon_io import parse_table_toon
from tests.conftest import SAMPLE_TOON


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def mock_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSDEN_TEST_MODE", "1")


def _save_sample_table() -> None:
    doc = parse_table_toon(SAMPLE_TOON)
    doc = table_service.derive_all(doc)
    table_service.save_table("users", doc)
    table_service.rebuild_index()


def test_トップページがHTMLを返す(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_存在しないテーブルの詳細は404(client: TestClient) -> None:
    resp = client.get("/tables/nonexistent")
    assert resp.status_code == 404


def test_テーブル詳細ページにタブが含まれる(client: TestClient) -> None:
    # Arrange
    _save_sample_table()

    # Act
    resp = client.get("/tables/users")

    # Assert
    assert resp.status_code == 200
    assert "論理設計" in resp.text
    assert "物理設計" in resp.text
    assert "DoA" in resp.text
    assert "ユーザー" in resp.text


def test_AI経由でテーブルを作成する(
    client: TestClient, mock_openai: None
) -> None:
    resp = client.post(
        "/api/tables",
        data={"prompt": "テーブルを作って"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert table_service.table_exists("stub_table")


def test_AI経由でテーブルを更新する(
    client: TestClient, mock_openai: None
) -> None:
    _save_sample_table()
    resp = client.post(
        "/api/tables/users",
        data={"prompt": "カラムを追加"},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_テーブルを削除する(client: TestClient) -> None:
    _save_sample_table()
    resp = client.delete("/api/tables/users")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "name": "users"}
    assert not table_service.table_exists("users")


def test_存在しないテーブルの削除は404(client: TestClient) -> None:
    resp = client.delete("/api/tables/nonexistent")
    assert resp.status_code == 404


class TestTableNameValidation:
    @pytest.mark.parametrize(
        "name", [".hidden", "UPPER", "123start"]
    )
    def test_不正なテーブル名の更新は422(
        self, client: TestClient, mock_openai: None, name: str
    ) -> None:
        resp = client.post(
            f"/api/tables/{name}", data={"prompt": "テスト"}
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "name", [".hidden", "UPPER", "123start"]
    )
    def test_不正なテーブル名の削除は422(
        self, client: TestClient, name: str
    ) -> None:
        resp = client.delete(f"/api/tables/{name}")
        assert resp.status_code == 422


class TestHtmxHxRedirect:
    HX_HEADERS = {"HX-Request": "true"}

    def test_テーブル作成でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None
    ) -> None:
        resp = client.post(
            "/api/tables",
            data={"prompt": "テスト"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "HX-Redirect" in resp.headers

    def test_テーブル更新でHXリダイレクトを返す(
        self, client: TestClient, mock_openai: None
    ) -> None:
        _save_sample_table()
        resp = client.post(
            "/api/tables/users",
            data={"prompt": "カラムを追加"},
            headers=self.HX_HEADERS,
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "/tables/users" in resp.headers["HX-Redirect"]


class TestSseEndpoints:
    @pytest.mark.parametrize(
        "url",
        ["/api/sse/rebuild-index", "/api/sse/rebuild-er"],
    )
    def test_SSEエンドポイントがイベントストリームを返す(
        self, client: TestClient, url: str
    ) -> None:
        with client.stream("GET", url) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = b"".join(resp.iter_bytes()).decode()
            assert "event: complete" in body
```

- [ ] **Step 6: E2E テストを更新する**

`tests/e2e/test_physical_design_page.py` を削除する。

```bash
git rm tests/e2e/test_physical_design_page.py
```

`tests/e2e/test_table_detail_page.py` と `tests/e2e/test_navigation.py` から物理設計ページへの遷移テストを削除し、タブ切り替え UI のテストを追加する。具体的な変更は E2E テストファイルの内容を読んで判断する。

- [ ] **Step 7: .data/ をクリアする**

```bash
rm -f .data/*.tsv .data/*.md .data/*.mmd .data/*.yaml
```

`index.yaml` の初期状態を作成する。

```bash
echo "next_table_id: 1" > .data/index.yaml
```

- [ ] **Step 8: 全テストがパスすることを確認する**

```bash
uv run task test
```

Expected: ALL PASS, coverage >= 80%

- [ ] **Step 9: lint + typecheck**

```bash
uv run task lint && uv run task typecheck
```

- [ ] **Step 10: コミット**

```bash
git add -A
git commit -m "feat: ルーター・テンプレートを TOON 統合ページに移行する

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
