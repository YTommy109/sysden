import logging
import re

from app.config import get_data_dir
from app.models import Column, IndexDocument, TableMeta, TableSummary, ToonDocument

logger = logging.getLogger(__name__)

_ARRAY_HEADER_RE = re.compile(r"^(\w+)\[(\d+)\]\{(.+)\}:$")
_SECTION_HEADER_RE = re.compile(r"^(\w+):$")
_KV_RE = re.compile(r"^  (\w+):\s*(.*)$")
_INDEX_STEM = "index"

_COLUMNS_FIELDS = [
    "symbol",
    "logical_name",
    "physical_name",
    "type",
    "nullable",
    "pk",
    "unique",
    "default",
    "fk_target",
    "description",
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
                sections.append((current_name, current_header, current_fields, current_lines))
            if array_m:
                current_name = array_m.group(1)
                current_header = line
                current_fields = array_m.group(3).split(",")
            else:
                assert section_m is not None
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
        if m := _KV_RE.match(line):
            result[m.group(1)] = m.group(2).strip()
    return result


def _parse_array_rows(fields: list[str], lines: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        values = stripped.split(",", maxsplit=len(fields) - 1)
        while len(values) < len(fields):
            values.append("")
        rows.append(dict(zip(fields, values, strict=False)))
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
    """TOON テキストをパースしてテーブルドキュメントを生成する。

    Args:
        text: TOON 形式のテキスト。

    Returns:
        パース結果の ToonDocument。
    """
    sections = _parse_sections(text)
    meta_dict: dict[str, str] = {}
    columns: list[Column] = []
    logical: list[dict[str, str]] | None = None
    physical: list[dict[str, str]] | None = None
    dao: list[dict[str, str]] | None = None

    for name, _header, fields, lines in sections:
        match name:
            case "meta":
                meta_dict = _parse_kv_lines(lines)
            case "columns" if fields:
                columns = [Column(**row) for row in _parse_array_rows(fields, lines)]
            case "logical" if fields:
                logical = _parse_array_rows(fields, lines)
            case "physical" if fields:
                physical = _parse_array_rows(fields, lines)
            case "dao" if fields:
                dao = _parse_array_rows(fields, lines)

    meta = TableMeta(**meta_dict)
    return ToonDocument(meta=meta, columns=columns, logical=logical, physical=physical, dao=dao)


def parse_index_toon(text: str) -> IndexDocument:
    """TOON テキストをパースしてインデックスドキュメントを生成する。

    Args:
        text: インデックス TOON 形式のテキスト。

    Returns:
        パース結果の IndexDocument。
    """
    sections = _parse_sections(text)
    description = ""
    rules: list[str] = []
    tables: list[TableSummary] = []
    er_diagram = ""

    for name, _header, fields, lines in sections:
        match name:
            case "meta":
                kv = _parse_kv_lines(lines)
                description = kv.get("description", "")
            case "rules":
                rules = _parse_list_lines(lines)
            case "tables" if fields:
                tables = [TableSummary(**row) for row in _parse_array_rows(fields, lines)]
            case "er_diagram":
                er_diagram = _parse_text_block(lines)

    return IndexDocument(description=description, rules=rules, tables=tables, er_diagram=er_diagram)


def parse_toon_tables(text: str) -> list[ToonDocument]:
    """複数テーブルを含む TOON テキストをパースする。

    ``meta:`` の出現位置でテキストを分割し、各チャンクを個別にパースする。

    Args:
        text: 複数テーブル定義を含む TOON テキスト。

    Returns:
        パースされた ToonDocument のリスト。
    """
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


def _serialize_array_section(name: str, fields: list[str], rows: list[dict[str, str]]) -> str:
    header = f"{name}[{len(rows)}]{{{','.join(fields)}}}:"
    lines = [header]
    for row in rows:
        values = [row.get(f, "") for f in fields]
        lines.append(f"  {','.join(values)}")
    return "\n".join(lines)


def serialize_table_toon(doc: ToonDocument) -> str:
    """ToonDocument を TOON テキストにシリアライズする。

    Args:
        doc: シリアライズ対象の ToonDocument。

    Returns:
        TOON 形式のテキスト。
    """
    parts: list[str] = []

    parts.append("meta:")
    if doc.meta.symbol is not None:
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

    if doc.dao is not None:
        fields = list(doc.dao[0].keys()) if doc.dao else []
        parts.append("")
        parts.append(_serialize_array_section("dao", fields, doc.dao))

    return "\n".join(parts) + "\n"


def serialize_index_toon(index: IndexDocument) -> str:
    """IndexDocument を TOON テキストにシリアライズする。

    Args:
        index: シリアライズ対象の IndexDocument。

    Returns:
        インデックス TOON 形式のテキスト。
    """
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
        parts.append(_serialize_array_section("tables", table_fields, table_dicts))

    if index.er_diagram:
        parts.append("")
        parts.append("er_diagram:")
        for line in index.er_diagram.splitlines():
            parts.append(f"  {line}")

    return "\n".join(parts) + "\n"


def read_toon(name: str) -> ToonDocument:
    """テーブルの TOON ファイルを読み込んでパースする。

    Args:
        name: テーブル名。

    Returns:
        パース結果の ToonDocument。

    Raises:
        FileNotFoundError: 指定テーブルのファイルが存在しない場合。
    """
    path = get_data_dir() / f"{name}.toon"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    text = path.read_text(encoding="utf-8")
    return parse_table_toon(text)


def write_toon(name: str, doc: ToonDocument) -> None:
    """ToonDocument を TOON ファイルに書き込む。

    Args:
        name: テーブル名。
        doc: 書き込む ToonDocument。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.toon"
    path.write_text(serialize_table_toon(doc), encoding="utf-8")
    logger.info("TOON 書き込み: table=%s", name)


def read_index_toon() -> IndexDocument:
    """インデックス TOON ファイルを読み込む。

    ファイルが存在しない場合はデフォルト値の IndexDocument を返す。

    Returns:
        インデックスの IndexDocument。
    """
    path = get_data_dir() / f"{_INDEX_STEM}.toon"
    if not path.exists():
        return IndexDocument(
            description="テーブル設計インデックス", rules=[], tables=[], er_diagram=""
        )
    text = path.read_text(encoding="utf-8")
    return parse_index_toon(text)


def write_index_toon(doc: IndexDocument) -> None:
    """IndexDocument をインデックス TOON ファイルに書き込む。

    Args:
        doc: 書き込む IndexDocument。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_INDEX_STEM}.toon"
    path.write_text(serialize_index_toon(doc), encoding="utf-8")
    logger.info("インデックス TOON 書き込み")
