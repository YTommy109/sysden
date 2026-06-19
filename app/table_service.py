import csv

from app.config import get_data_dir

TSV_HEADERS = ["column_name", "type", "nullable", "pk", "unique", "default", "description"]
_INDEX_STEM = "index"


def list_tables() -> list[str]:
    """データディレクトリに存在するテーブル名の一覧を返す。

    Returns:
        ソート済みのテーブル名リスト。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return sorted(f.stem for f in d.glob("*.tsv") if f.stem != _INDEX_STEM)


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


def delete_table(name: str) -> None:
    """テーブルの TSV ファイルを削除する。

    Args:
        name: テーブル名。

    Raises:
        FileNotFoundError: テーブルが存在しない場合。
    """
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    path.unlink()


def tsv_to_markdown(rows: list[dict[str, str]]) -> str:
    """カラム定義の辞書リストを Markdown テーブルに変換する。

    Args:
        rows: カラム定義の辞書リスト。空の場合はプレースホルダを返す。

    Returns:
        Markdown テーブル文字列。
    """
    if not rows:
        return "_（カラム定義なし）_"
    headers = list(rows[0].keys())
    sep = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        cells = [row.get(h, "") for h in headers]
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


def rebuild_index() -> None:
    """テーブル一覧 (index.tsv) と ER 図 (index.mmd) を再生成する。

    テーブル追加・削除の後に呼び出す。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    names = list_tables()

    lines = ["name"] + names
    (d / f"{_INDEX_STEM}.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    er = tables_to_er_diagram()
    (d / f"{_INDEX_STEM}.mmd").write_text(er, encoding="utf-8")


def read_index_tables() -> list[str]:
    """index.tsv からテーブル名一覧を読み込む。

    Returns:
        テーブル名のリスト。ファイルが存在しなければ空リスト。
    """
    path = get_data_dir() / f"{_INDEX_STEM}.tsv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [row["name"] for row in reader]


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


def _resolve_fk_target(column_name: str, table_names: set[str]) -> str | None:
    """``_id`` サフィックスのカラム名から参照先テーブルを推定する。

    Args:
        column_name: カラム名（例: ``user_id``）。
        table_names: 存在するテーブル名のセット。

    Returns:
        一致したテーブル名。見つからなければ ``None``。
    """
    if not column_name.endswith("_id"):
        return None
    prefix = column_name[: -len("_id")]
    for candidate in (prefix, f"{prefix}s"):
        if candidate in table_names:
            return candidate
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
    lines = ["erDiagram"]
    relations: list[str] = []

    for name in names:
        try:
            rows = read_tsv(name)
        except FileNotFoundError:
            continue
        for row in rows:
            target = _resolve_fk_target(row.get("column_name", ""), name_set)
            if target is None or target == name:
                continue
            nullable = row.get("nullable", "NO").upper() == "YES"
            arrow = "|o--o{" if nullable else "||--o{"
            relations.append(f'    {target} {arrow} {name} : ""')

    lines.extend(f"    {name}" for name in names)
    lines.extend(relations)
    return "\n".join(lines)
