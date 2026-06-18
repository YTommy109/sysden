import sys
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.routing import APIRoute


def test_events_route_is_registered() -> None:
    # Remove cached app module to force fresh import
    for key in list(sys.modules.keys()):
        if key.startswith("app") or key.startswith("sqlmodel"):
            del sys.modules[key]

    # Patch before importing to avoid initialization errors
    with (
        patch("anthropic.Anthropic"),
        patch("app.ai_service.initialize_agent", new_callable=AsyncMock),
    ):
        # Clear SQLModel registry if it exists
        try:
            from sqlmodel import SQLModel

            SQLModel.metadata.clear()
        except Exception:
            pass

        from app.main import app

        # Collect all paths from the app's routes
        paths: list[str] = []
        for route in app.routes:
            if isinstance(route, APIRoute):
                paths.append(route.path)
            elif hasattr(route, "original_router"):
                # Handle _IncludedRouter
                original_router: Any = getattr(route, "original_router")
                for subroute in original_router.routes:
                    if isinstance(subroute, APIRoute):
                        paths.append(subroute.path)

        assert "/events" in paths
