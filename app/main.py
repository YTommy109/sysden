from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.routers import api, html  # noqa: E402

app = FastAPI(title="sysden")
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent.parent / "static")), name="static"
)
app.include_router(api.router)
app.include_router(html.router)
