import csv

from app.config import get_data_dir

TSV_HEADERS = ["column_name", "type", "nullable", "pk", "unique", "default", "description"]


def list_tables() -> list[str]:
    """データディレクトリに存在するテーブル名の一覧を返す。

    Returns:
        ソート済みのテーブル名リスト。
    """
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return sorted(f.stem for f in d.glob("*.tsv"))


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
