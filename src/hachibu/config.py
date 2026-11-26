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
        )
