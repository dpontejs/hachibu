"""Fábrica da aplicação FastAPI."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from hachibu import alimentos, auth, diario, perfil
from hachibu.coach import rotas as coach_rotas
from hachibu.config import Settings
from hachibu.db import connect, migrate


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Hachibu")
    app.state.settings = settings
    conn = connect(settings.db_path)
    migrate(conn)
    alimentos.carregar_taco(conn)
    conn.close()
    app.state.login_limiter = auth.LoginLimiter()
    app.state.signup_limiter = auth.LoginLimiter(max_global=20)
    app.include_router(auth.router)
    app.include_router(perfil.router)
    app.include_router(diario.router)
    app.include_router(alimentos.router)
    app.include_router(coach_rotas.router)
    app.state.modelo_coach = _modelo_coach(settings)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    if settings.static_dir:
        _servir_spa(app, Path(settings.static_dir).resolve())
    return app


def _modelo_coach(settings: Settings):
    """Gemini do coach; sem chave, o coach responde 503 e o resto do app funciona."""
    if not settings.gemini_api_key:
        return None
    from langchain.chat_models import init_chat_model

    # O Gemini 3.x usa amostragem fixa e ignora temperature; por isso não passamos.
    # Sem timeout, o cliente espera para sempre e repete 6 vezes: segura threads e a tela fica "pensando".
    return init_chat_model(settings.coach_modelo, api_key=settings.gemini_api_key, timeout=30, max_retries=2)


def _servir_spa(app: FastAPI, dist: Path) -> None:
    """Serve o build do React; rotas desconhecidas fora de /api devolvem o index.html (React Router)."""
    index = dist / "index.html"

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        if caminho == "api" or caminho.startswith("api/"):
            raise HTTPException(404, "Not Found")
        arquivo = (dist / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(dist):
            # Os assets têm hash no nome: podem ficar em cache para sempre.
            imutavel = caminho.startswith("assets/")
            cache = "public, max-age=31536000, immutable" if imutavel else "no-cache"
            return FileResponse(arquivo, headers={"Cache-Control": cache})
        if caminho.startswith("assets/"):
            # Asset de um build antigo: 404, nunca o index.html (o navegador recusaria o módulo e o app
            # ficaria em branco).
            raise HTTPException(404, "Not Found")
        # O index sempre revalida, para um deploy novo chegar a quem está com o app aberto.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def from_env() -> FastAPI:
    return create_app(Settings.from_env())
