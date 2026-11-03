from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tracelume import __version__
from tracelume.api.routes import router
from tracelume.config import get_settings
from tracelume.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    for d in (s.evidence_dir, s.workspace_dir, s.import_dir):
        d.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Tracelume", version=__version__, lifespan=lifespan)
    app.include_router(router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    static = Path(__file__).parent / "static"
    if static.is_dir():  # built frontend, bundled in the release image
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            f = (static / path).resolve()
            if path and f.is_file() and f.is_relative_to(static.resolve()):
                return FileResponse(f)
            return FileResponse(static / "index.html")

    return app


app = create_app()
