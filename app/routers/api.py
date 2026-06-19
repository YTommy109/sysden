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
        name, tsv = ai_service.create_table_design(prompt)
    else:
        tsv = ai_service.generate_table_design(prompt)
    if table_service.table_exists(name):
        raise HTTPException(status_code=409, detail=f"Table '{name}' already exists")
    table_service.write_tsv(name, tsv)
    return RedirectResponse(url=f"/tables/{name}", status_code=303)


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


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    try:
        table_service.delete_table(name)
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found") from err
    return {"status": "deleted", "name": name}
