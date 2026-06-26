from pathlib import Path

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": True}).enable("table")

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


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


def _dict_table_html(rows: list[dict[str, str]] | None) -> str:
    if not rows:
        return ""
    return _md.render(_dict_list_to_markdown_table(rows))


def _logical_table_html(rows: list[dict[str, str]] | None) -> str:
    html = _dict_table_html(rows)
    return html.replace(
        "<td>* ",
        '<td><span style="color:red;font-weight:bold;">*</span> ',
    )


templates.env.filters["dict_table_html"] = _dict_table_html
templates.env.filters["logical_table_html"] = _logical_table_html
