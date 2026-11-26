"""Fábrica da aplicação FastAPI."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from hachibu import auth, diario, perfil
from hachibu.config import Settings
from hachibu.db import connect, migrate


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Hachibu")
    app.state.settings = settings
    conn = connect(settings.db_path)
    migrate(conn)
    conn.close()
    app.state.login_limiter = auth.LoginLimiter()
    app.include_router(auth.router)
    app.include_router(perfil.router)
    app.include_router(diario.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    if settings.static_dir:
        _servir_spa(app, Path(settings.static_dir).resolve())
    return app


def _servir_spa(app: FastAPI, dist: Path) -> None:
    """Serve o build do React; rotas desconhecidas fora de /api devolvem o index.html (React Router)."""
    index = dist / "index.html"

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(404, "Not Found")
        arquivo = (dist / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(dist):
            return FileResponse(arquivo)
        return FileResponse(index)


def from_env() -> FastAPI:
    return create_app(Settings.from_env())
