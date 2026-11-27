"""Configuração lida do ambiente."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    session_secret: str
    invite_code: str
    app_tz: str = "America/Sao_Paulo"
    cookie_secure: bool = True
    # Pasta com o build do React (web/dist); None = só a API.
    static_dir: str | None = None
    gemini_api_key: str | None = None
    coach_modelo: str = "google_genai:gemini-3.6-flash"
    coach_limite_diario: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        secret = os.environ.get("SESSION_SECRET", "")
        invite = os.environ.get("INVITE_CODE", "")
        if len(secret) < 32 or not invite:
            raise RuntimeError("Defina SESSION_SECRET (32+ caracteres) e INVITE_CODE.")
        return cls(
            db_path=os.environ.get("DB_PATH", "data/hachibu.db"),
            session_secret=secret,
            invite_code=invite,
            app_tz=os.environ.get("APP_TZ", "America/Sao_Paulo"),
            cookie_secure=os.environ.get("COOKIE_SECURE", "true").lower() != "false",
            static_dir=os.environ.get("STATIC_DIR") or None,
            gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
            coach_modelo=os.environ.get("COACH_MODELO", "google_genai:gemini-3.6-flash"),
            coach_limite_diario=int(os.environ.get("COACH_LIMITE_DIARIO", "60")),
        )
