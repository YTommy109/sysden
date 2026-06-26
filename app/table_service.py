import logging
import re

from app import ai_service, symbol_service
from app.config import get_data_dir
from app.derive_service import derive_all
from app.models import IndexDocument, TableSummary, ToonDocument
from app.toon_io import (
    read_index_toon,
    read_toon,
    write_index_toon,
    write_toon,
)

logger = logging.getLogger(__name__)

_TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def validate_table_name(name: str) -> bool:
    """テーブル名が命名規約に適合するか検証する。

    Args:
        name: 検証するテーブル名。

    Returns:
        ``^[a-z][a-z0-9_]{0,63}$`` に適合すれば True。
    """
    return _TABLE_NAME_RE.fullmatch(name) is not None


def _require_valid_name(name: str) -> None:
    if not validate_table_name(name):
        raise ValueError(f"Invalid table name: '{name}'")


def get_index() -> IndexDocument:
    """インデックスドキュメントを取得する。

    Returns:
        IndexDocument（テーブル一覧・ルール・ER 図を含む）。
    """
    return read_index_toon()


def table_exists(name: str) -> bool:
    """指定テーブルの TOON ファイルが存在するか判定する。

    Args:
        name: テーブル名。

    Returns:
        ファイルが存在すれば True。
    """
    return (get_data_dir() / f"{name}.toon").exists()


def list_tables() -> list[TableSummary]:
    """インデックスからテーブル要約一覧を取得する。

    Returns:
        TableSummary のリスト。
    """
    index = read_index_toon()
    return index.tables


def get_table(name: str) -> ToonDocument:
    """テーブルの TOON ドキュメントを読み込む。

    Args:
        name: テーブル名。

    Returns:
        読み込んだ ToonDocument。

    Raises:
        FileNotFoundError: 指定テーブルが存在しない場合。
    """
    return read_toon(name)


def save_table(name: str, doc: ToonDocument) -> None:
    """テーブルの TOON ドキュメントをファイルに保存する。

    Args:
        name: テーブル名。
        doc: 保存する ToonDocument。
    """
    write_toon(name, doc)
    logger.info("テーブル保存: table=%s", name)


def delete_table(name: str) -> None:
    """テーブルの TOON ファイルを削除する。

    Args:
        name: テーブル名。

    Raises:
        ValueError: テーブル名が不正な場合。
        FileNotFoundError: 指定テーブルが存在しない場合。
    """
    _require_valid_name(name)
    path = get_data_dir() / f"{name}.toon"
    if not path.exists():
        logger.warning("テーブル削除失敗: table=%s (存在しない)", name)
        raise FileNotFoundError(f"Table '{name}' not found")
    path.unlink()
    logger.info("テーブル削除: table=%s", name)


def generate_er_diagram(tables: list[TableSummary] | None = None) -> str:
    """テーブル一覧から Mermaid ER 図を生成する。

    FK 参照からリレーションを自動検出する。

    Args:
        tables: テーブル要約リスト。None の場合はインデックスから取得する。

    Returns:
        Mermaid ER 図文字列。テーブルがなければ空文字列。
    """
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
    """全 TOON ファイルを走査してインデックスと ER 図を再構築する。"""
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


def create_tables_from_ai(prompt: str) -> list[str]:
    """AI にテーブル設計を依頼し、検証・保存してテーブル名を返す。

    シンボル採番・FK プレースホルダ置換・導出を行い、
    途中失敗時は作成済みファイルをロールバックする。

    Args:
        prompt: ユーザーからの依頼テキスト。

    Returns:
        作成されたテーブル名のリスト。

    Raises:
        ValueError: AI が生成したテーブル名が不正な場合。
        FileExistsError: 同名テーブルが既に存在する場合。
    """
    index = read_index_toon()
    designs = ai_service.create_table_design(
        prompt=prompt,
        rules=index.rules,
        existing_tables=index.tables,
    )

    for doc in designs:
        _require_valid_name(doc.meta.physical_name)
        if table_exists(doc.meta.physical_name):
            raise FileExistsError(f"Table '{doc.meta.physical_name}' already exists")

    table_symbols = [symbol_service.allocate_table_symbol() for _ in designs]
    placeholder_map: dict[str, str] = {}
    for i, _doc in enumerate(designs):
        placeholder_map[f"NEW_{i + 1}"] = table_symbols[i]
    designs = symbol_service.remap_placeholders(
        designs, placeholder_map, table_symbols=table_symbols
    )

    written: list[str] = []
    try:
        for doc in designs:
            doc = derive_all(doc)
            name = doc.meta.physical_name
            save_table(name, doc)
            written.append(name)
    except Exception:
        for name in written:
            delete_table(name)
        raise
    rebuild_index()
    names = [d.meta.physical_name for d in designs]
    logger.info("テーブル作成完了: tables=%s", names)
    return names


def update_table_from_ai(name: str, prompt: str) -> None:
    """AI に既存テーブルの設計更新を依頼し、保存する。

    Args:
        name: 更新対象のテーブル名。
        prompt: ユーザーからの変更依頼テキスト。

    Raises:
        ValueError: テーブル名が不正な場合。
        FileNotFoundError: テーブルが存在しない場合。
    """
    _require_valid_name(name)
    current = get_table(name)
    index = read_index_toon()
    updated = ai_service.update_table_design(
        prompt=prompt,
        current=current,
        rules=index.rules,
        existing_tables=index.tables,
    )
    updated = updated.model_copy(
        update={"meta": updated.meta.model_copy(update={"symbol": current.meta.symbol})}
    )
    updated = derive_all(updated)
    save_table(name, updated)
    rebuild_index()
    logger.info("テーブル更新完了: table=%s", name)
