from typing import Annotated

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import RedirectResponse

from app import ai_service, table_service
from app.config import get_data_dir

router = APIRouter(prefix="/api")


@router.post("/tables")
def create_table(
    name: Annotated[str, Form()],
    prompt: Annotated[str, Form()],
) -> RedirectResponse:
    if table_service.table_exists(name):
        raise HTTPException(status_code=409, detail=f"Table '{name}' already exists")
    tsv = ai_service.generate_table_design(prompt)
    table_service.write_tsv(name, tsv)
    return RedirectResponse(url=f"/tables/{name}", status_code=303)


@router.post("/tables/{name}")
def update_table(
    name: str,
    prompt: Annotated[str, Form()],
) -> RedirectResponse:
    try:
        current_tsv = (get_data_dir() / f"{name}.tsv").read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")
    tsv = ai_service.generate_table_design(prompt, current_tsv)
    table_service.write_tsv(name, tsv)
    return RedirectResponse(url=f"/tables/{name}", status_code=303)


@router.delete("/tables/{name}")
def delete_table(name: str) -> dict[str, str]:
    try:
        table_service.delete_table(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")
    return {"status": "deleted", "name": name}
