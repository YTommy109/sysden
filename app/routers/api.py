from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse

from app import ai_service, table_service

router = APIRouter(prefix="/api")


@router.post("/tables")
def create_table(
    prompt: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    if name is None:
        tables = ai_service.create_table_design(prompt)
    else:
        tsv = ai_service.generate_table_design(prompt)
        default_md = f"# {name} テーブル\n\n## テーブル設計\n\n![[{name}.tsv]]\n"
        tables = [(name, tsv, default_md)]
    for tbl_name, _, _ in tables:
        if table_service.table_exists(tbl_name):
            raise HTTPException(status_code=409, detail=f"Table '{tbl_name}' already exists")
    for tbl_name, tbl_tsv, tbl_md in tables:
        table_service.write_tsv(tbl_name, tbl_tsv)
        if tbl_md:
            table_service.write_markdown(tbl_name, tbl_md)
    table_service.rebuild_index()
    if len(tables) == 1:
        return RedirectResponse(url=f"/tables/{tables[0][0]}", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    prompt: Annotated[str, Form()],
) -> RedirectResponse:
    try:
        current_tsv = table_service.read_tsv_raw(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    tsv = ai_service.generate_table_design(prompt, current_tsv)
    table_service.write_tsv(name, tsv)
    return RedirectResponse(url=f"/tables/{name}", status_code=303)


@router.post("/rebuild-index-tables")
def rebuild_index_tables() -> RedirectResponse:
    """テーブル一覧 (index.tsv) と ER 図 (index.mmd) を再生成してトップページへリダイレクトする。"""
    table_service.rebuild_index_tables()
    table_service.rebuild_er_diagram_file()
    return RedirectResponse(url="/", status_code=303)


@router.post("/rebuild-er-diagram")
def rebuild_er_diagram() -> RedirectResponse:
    """ER 図 (index.mmd) を再生成してトップページへリダイレクトする。"""
    table_service.rebuild_er_diagram_file()
    return RedirectResponse(url="/", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    table_service.rebuild_index()
    return {"status": "deleted", "name": name}
