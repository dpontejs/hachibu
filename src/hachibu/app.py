"""Fábrica da aplicação FastAPI."""

from fastapi import FastAPI

from hachibu.config import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Hachibu")
    app.state.settings = settings

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    return app


def from_env() -> FastAPI:
    return create_app(Settings.from_env())
