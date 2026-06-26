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
    path.write_text(yaml.dump({"next_table_id": next_id}), encoding="utf-8")


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
                col = col.model_copy(update={"fk_target": symbol_map[col.fk_target]})
            new_columns.append(col)

        result.append(doc.model_copy(update={"meta": meta, "columns": new_columns}))
    return result
