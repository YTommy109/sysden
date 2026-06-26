from pydantic import BaseModel


class Column(BaseModel):
    symbol: str
    logical_name: str
    physical_name: str
    type: str
    nullable: str
    pk: str
    unique: str
    default: str = ""
    fk_target: str = ""
    description: str = ""


class TableMeta(BaseModel):
    symbol: str | None = None
    logical_name: str
    physical_name: str
    description: str


class ToonDocument(BaseModel):
    meta: TableMeta
    columns: list[Column]
    logical: list[dict[str, str]] | None = None
    physical: list[dict[str, str]] | None = None
    dao: list[dict[str, str]] | None = None


class TableSummary(BaseModel):
    symbol: str
    name: str
    logical_name: str
    description: str


class IndexDocument(BaseModel):
    description: str
    rules: list[str]
    tables: list[TableSummary]
    er_diagram: str
