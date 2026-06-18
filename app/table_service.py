import csv

from app.config import get_data_dir

TSV_HEADERS = ["column_name", "type", "nullable", "pk", "unique", "default", "description"]


def list_tables() -> list[str]:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return sorted(f.stem for f in d.glob("*.tsv"))


def read_tsv(name: str) -> list[dict[str, str]]:
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def write_tsv(name: str, tsv_content: str) -> None:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.tsv"
    path.write_text(tsv_content.strip() + "\n", encoding="utf-8")


def delete_table(name: str) -> None:
    path = get_data_dir() / f"{name}.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Table '{name}' not found")
    path.unlink()


def tsv_to_markdown(rows: list[dict[str, str]]) -> str:
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
    return (get_data_dir() / f"{name}.tsv").exists()
