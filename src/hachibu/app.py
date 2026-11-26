"""Fábrica da aplicação FastAPI."""

from fastapi import FastAPI

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

    return app


def from_env() -> FastAPI:
    return create_app(Settings.from_env())
