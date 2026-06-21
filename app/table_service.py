import csv
import logging
import re

from app.config import get_data_dir

logger = logging.getLogger(__name__)

TSV_HEADERS = ["column_name", "type", "nullable", "pk", "unique", "default", "description"]
_INDEX_STEM = "index"
_TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def validate_table_name(name: str) -> bool:
    """テーブル名が安全な形式か検証する。

    英小文字で始まり、英小文字・数字・アンダースコアのみで構成され、
    1〜64 文字であること。

    Args:
        name: テーブル名。

    Returns:
        有効なら True。
    """
    return _TABLE_NAME_RE.fullmatch(name) is not None


_PHYSICAL_PREFIX = "physical_"


def list_tables() -> list[str]:
    """データディレクトリに存在するテーブル名の一覧を返す。

    Returns:
        ソート済みのテーブル名リスト。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return sorted(
        f.stem
        for f in d.glob("*.tsv")
        if f.stem != _INDEX_STEM and not f.stem.startswith(_PHYSICAL_PREFIX)
    )


def read_tsv_raw(name: str) -> str:
    """指定テーブルの TSV を生文字列として読み込む。

    Args:
        name: テーブル名。

    Returns:
        TSV ファイルの内容。

    Raises:
        FileNotFoundError: テーブルが存在しない場合。
    """
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    return path.read_text(encoding="utf-8")


def read_tsv(name: str) -> list[dict[str, str]]:
    """指定テーブルの TSV を読み込み、辞書のリストとして返す。

    Args:
        name: テーブル名。

    Returns:
        各行がカラム名→値の辞書になったリスト。

    Raises:
        FileNotFoundError: テーブルが存在しない場合。
    """
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def write_tsv(name: str, tsv_content: str) -> None:
    """テーブルの TSV をファイルに書き込む。

    Args:
        name: テーブル名。
        tsv_content: タブ区切りのカラム定義文字列。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")
    logger.info("TSV 書き込み: table=%s", name)


def delete_table(name: str) -> None:
    """テーブルの TSV ファイルと markdown ファイルを削除する。

    Args:
        name: テーブル名。

    Raises:
        FileNotFoundError: テーブルが存在しない場合。
    """
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        logger.warning("テーブル削除失敗: table=%s (存在しない)", name)
        raise FileNotFoundError(f"Table '{name}' not found")
    path.unlink()
    md_path = get_data_dir() / f"{name}.md"
    if md_path.exists():
        md_path.unlink()
    logger.info("テーブル削除: table=%s", name)


def write_markdown(name: str, content: str) -> None:
    """テーブル説明の markdown をファイルに書き込む。

    Args:
        name: テーブル名。
        content: markdown 文字列。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    logger.info("Markdown 書き込み: table=%s", name)


def read_markdown(name: str) -> str | None:
    """テーブル説明の markdown を読み込む。

    Args:
        name: テーブル名。

    Returns:
        markdown 文字列。ファイルが存在しなければ None。
    """
    path = get_data_dir() / f"{name}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


_HEADING_RE = re.compile(r"^# (.+)$", re.MULTILINE)
_TITLE_LINE_RE = re.compile(r"^# [^\n]+\n*")


def read_table_display_name(name: str) -> str:
    """テーブルの表示名を markdown の見出しから取得する。

    Args:
        name: テーブルのファイル名（拡張子なし）。

    Returns:
        markdown の最初の # 見出しから取得した表示名。
        markdown がない場合や見出しがない場合はファイル名をそのまま返す。
    """
    md = read_markdown(name)
    if md is None:
        return name
    m = _HEADING_RE.search(md)
    if m:
        return m.group(1).strip()
    return name


def strip_title_heading(content: str) -> str:
    """markdown から最初の # 見出し行を除去する。

    テンプレートの h1 と重複するため、レンダリング前に呼び出す。

    Args:
        content: markdown 文字列。

    Returns:
        # 見出しが除去された markdown 文字列。
    """
    return _TITLE_LINE_RE.sub("", content, count=1)


_EMBED_RE = re.compile(r"!\[\[([A-Za-z0-9_]+\.tsv)\]\]")


def render_markdown_with_embeds(content: str) -> str:
    """markdown 内の ![[*.tsv]] を TSV テーブルの markdown 表現に展開する。

    Args:
        content: 埋め込みリンクを含む markdown 文字列。

    Returns:
        埋め込みが展開された markdown 文字列。
    """

    def _replace(m: re.Match[str]) -> str:
        filename = m.group(1)
        name = filename.removesuffix(".tsv")
        try:
            rows = read_tsv(name)
        except FileNotFoundError:
            return f"_（{filename} が見つかりません）_"
        return tsv_to_markdown(rows)

    return _EMBED_RE.sub(_replace, content)


_DISPLAY_HEADERS = ["カラム名", "型", "ユニーク", "説明"]

_TYPE_MAP: dict[str, str] = {
    "DATE": "日付",
    "VARCHAR": "文字列",
    "DECIMAL": "固定小数点数",
    "INTEGER": "整数",
    "INT": "整数",
    "BIGINT": "整数",
    "SMALLINT": "整数",
    "TEXT": "テキスト",
    "BOOLEAN": "真偽値",
    "TIMESTAMPTZ": "タイムスタンプ",
    "TIMESTAMP": "タイムスタンプ",
}

_TYPE_PARAM_RE = re.compile(r"^([A-Za-z]+)(\(.+\))$")


def _translate_type(raw_type: str) -> str:
    """SQL 型名を日本語表記に変換する。"""
    m = _TYPE_PARAM_RE.match(raw_type)
    if m:
        base, params = m.group(1), m.group(2)
        return _TYPE_MAP.get(base.upper(), base) + params
    return _TYPE_MAP.get(raw_type.upper(), raw_type)


def _build_description(row: dict[str, str]) -> str:
    """description を説明セルとして返す。"""
    return row.get("description", "")


def tsv_to_markdown(rows: list[dict[str, str]]) -> str:
    """カラム定義の辞書リストを日本語ヘッダーの Markdown テーブルに変換する。

    TSV の 7 列（column_name, type, nullable, pk, unique, default, description）を
    表示用の 4 列（カラム名, 型, ユニーク, 説明）にマッピングする。
    型名は日本語に変換し、必須は * プレフィックス、PK は太字、FK は薄色で表現する。

    Args:
        rows: カラム定義の辞書リスト。空の場合はプレースホルダを返す。

    Returns:
        Markdown テーブル文字列。
    """
    if not rows:
        return "_（カラム定義なし）_"

    table_names = set(list_tables())
    dn_map = _build_display_name_map(table_names)

    sep = ["---"] * len(_DISPLAY_HEADERS)
    lines = [
        "| " + " | ".join(_DISPLAY_HEADERS) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        col_name = row.get("column_name", "")
        description = row.get("description", "")

        is_fk = _resolve_fk_target(col_name, table_names, description, dn_map) is not None
        is_pk = row.get("pk", "").upper() == "YES"

        if is_pk:
            name = f"**{col_name}**"
        elif is_fk:
            name = f'<span class="fk">{col_name}</span>'
        else:
            name = col_name

        col_type = _translate_type(row.get("type", ""))
        if row.get("nullable", "").upper() == "NO":
            col_type = f'<span class="required">*</span> {col_type}'
        cells = [
            name,
            col_type,
            "○" if row.get("unique", "").upper() == "YES" else "",
            _build_description(row),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def table_exists(name: str) -> bool:
    """指定テーブルの TSV ファイルが存在するか確認する。

    Args:
        name: テーブル名。

    Returns:
        存在すれば True。
    """
    return (get_data_dir() / f"{name}.tsv").exists()


def physical_design_exists(name: str) -> bool:
    return (get_data_dir() / f"{_PHYSICAL_PREFIX}{name}.tsv").exists()


def write_physical_tsv(name: str, tsv_content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")


def write_physical_doa_tsv(name: str, tsv_content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}_doa.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")


def write_physical_markdown(name: str, content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{_PHYSICAL_PREFIX}{name}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")


def read_physical_markdown(name: str) -> str | None:
    path = get_data_dir() / f"{_PHYSICAL_PREFIX}{name}.md"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def rebuild_index_tables() -> None:
    """テーブル一覧 (index.tsv) を再生成する。"""
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    names = list_tables()
    lines = ["name\tdisplay_name"]
    for name in names:
        display_name = read_table_display_name(name)
        lines.append(f"{name}\t{display_name}")
    (d / f"{_INDEX_STEM}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rebuild_er_diagram_file() -> None:
    """ER 図 (index.mmd) を再生成する。"""
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    er = tables_to_er_diagram()
    (d / f"{_INDEX_STEM}.mmd").write_text(er, encoding="utf-8")


def rebuild_index() -> None:
    """テーブル一覧 (index.tsv) と ER 図 (index.mmd) を再生成する。

    テーブル追加・削除の後に呼び出す。
    """
    rebuild_index_tables()
    rebuild_er_diagram_file()
    logger.info("インデックス再構築完了")


def read_index_tables() -> list[dict[str, str]]:
    """index.tsv からテーブル名一覧を読み込む。

    Returns:
        name と display_name を含む辞書のリスト。ファイルが存在しなければ空リスト。
    """
    path = get_data_dir() / f"{_INDEX_STEM}.tsv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [
            {"name": row["name"], "display_name": row.get("display_name", row["name"])}
            for row in reader
        ]


def read_er_diagram() -> str:
    """index.mmd から ER 図テキストを読み込む。

    Returns:
        mermaid erDiagram テキスト。ファイルが存在しないか空なら空文字列。
    """
    path = get_data_dir() / f"{_INDEX_STEM}.mmd"
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8").strip()
    return content


def _build_display_name_map(table_names: set[str]) -> dict[str, str]:
    """表示名からファイル名への逆引きマップを構築する。"""
    mapping: dict[str, str] = {}
    for name in table_names:
        display = read_table_display_name(name)
        if display != name:
            mapping[display] = name
    return mapping


def _resolve_fk_target(
    column_name: str,
    table_names: set[str],
    description: str = "",
    display_name_map: dict[str, str] | None = None,
) -> str | None:
    """カラム名または description から参照先テーブルを推定する。

    以下の順で判定し、最初にヒットしたテーブル名を返す:

    1. ``_id`` サフィックス（例: ``user_id`` → ``user`` / ``users``）
    2. description 中の「〇〇テーブル」表記（例: 「商品種類テーブルの識別子」→ ``product_types``）

    Args:
        column_name: カラム名（例: ``user_id``、``種類識別子``）。
        table_names: 存在するテーブル名（ファイル名）のセット。
        description: カラムの説明文。
        display_name_map: 表示名→ファイル名の逆引きマップ。

    Returns:
        一致したテーブル名（ファイル名）。見つからなければ ``None``。
    """
    if column_name.endswith("_id"):
        prefix = column_name[: -len("_id")]
        for candidate in (prefix, f"{prefix}s"):
            if candidate in table_names:
                return candidate

    match = re.search(r"(.+?)テーブル", description)
    if match:
        ref = match.group(1)
        if ref in table_names:
            return ref
        if display_name_map and ref in display_name_map:
            return display_name_map[ref]

    return None


def tables_to_er_diagram() -> str:
    """全テーブルの mermaid erDiagram テキストを生成する。

    ``_id`` サフィックスのカラムから外部キー関係を推定し、リレーション線を描く。

    Returns:
        テーブルが 1 件以上あれば erDiagram テキスト。0 件なら空文字列。
    """
    names = list_tables()
    if not names:
        return ""

    name_set = set(names)
    dn_map = _build_display_name_map(name_set)
    lines = ["erDiagram"]
    relations: list[str] = []

    for name in names:
        try:
            rows = read_tsv(name)
        except FileNotFoundError:
            continue
        for row in rows:
            target = _resolve_fk_target(
                row.get("column_name", ""),
                name_set,
                row.get("description", ""),
                dn_map,
            )
            if target is None or target == name:
                continue
            nullable = row.get("nullable", "NO").upper() == "YES"
            arrow = "|o--o{" if nullable else "||--o{"
            relations.append(f'    {target} {arrow} {name} : ""')

    lines.extend(f"    {name}" for name in names)
    lines.extend(relations)
    return "\n".join(lines)
