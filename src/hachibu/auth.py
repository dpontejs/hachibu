"""Cadastro com convite, login por e-mail e senha e sessão em cookie assinado.

O `user_id` de qualquer rota vem só daqui (`current_user`), nunca do corpo da requisição.
"""

import hmac
import threading
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, TimestampSigner
from pydantic import BaseModel, Field, field_validator

from hachibu.config import Settings
from hachibu.db import Db

COOKIE_NAME = "hachibu_session"
SESSION_MAX_AGE = 90 * 24 * 3600

router = APIRouter(prefix="/api")
_hasher = PasswordHasher()


class LoginLimiter:
    """Contador de falhas em memória (um processo só): 5 por IP em 10 min, 20 no total."""

    def __init__(self, max_falhas: int = 5, janela: timedelta = timedelta(minutes=10), max_global: int = 20):
        self.max_falhas = max_falhas
        self.janela = janela
        self.max_global = max_global
        self._falhas: list[tuple[datetime, str]] = []
        self._lock = threading.Lock()

    def bloqueado(self, ip: str, agora: datetime) -> bool:
        with self._lock:
            self._falhas = [(t, a) for t, a in self._falhas if agora - t < self.janela]
            por_ip = sum(1 for _, a in self._falhas if a == ip)
            return por_ip >= self.max_falhas or len(self._falhas) >= self.max_global

    def falhou(self, ip: str, agora: datetime) -> None:
        with self._lock:
            self._falhas.append((agora, ip))

    def acertou(self, ip: str) -> None:
        with self._lock:
            self._falhas = [(t, a) for t, a in self._falhas if a != ip]


def _normalizar_email(valor: str) -> str:
    email = valor.strip().lower()
    nome, _, dominio = email.partition("@")
    if not nome or "." not in dominio or " " in email:
        raise ValueError("e-mail inválido")
    return email


class SignupIn(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(min_length=8, max_length=128)
    convite: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _normalizar_email(v)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


def _signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.session_secret, salt="hachibu-session")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _abrir_sessao(response: Response, settings: Settings, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _signer(settings).sign(str(user_id)).decode(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def current_user(request: Request, db: Db) -> int:
    """Dependência: o id do usuário da sessão, ou 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "nao_autenticado")
    try:
        user_id = int(_signer(request.app.state.settings).unsign(token, max_age=SESSION_MAX_AGE).decode())
    except (BadSignature, ValueError):
        raise HTTPException(401, "nao_autenticado") from None
    existe = db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    if not existe:
        raise HTTPException(401, "nao_autenticado")
    return user_id


UserId = Annotated[int, Depends(current_user)]


@router.post("/auth/signup", status_code=201)
def signup(dados: SignupIn, request: Request, response: Response, db: Db) -> dict:
    settings: Settings = request.app.state.settings
    limiter: LoginLimiter = request.app.state.login_limiter
    ip, agora = _ip(request), datetime.now(UTC)
    if limiter.bloqueado(ip, agora):
        raise HTTPException(429, "muitas_tentativas")
    if not hmac.compare_digest(dados.convite.encode(), settings.invite_code.encode()):
        limiter.falhou(ip, agora)
        raise HTTPException(403, "convite_invalido")
    if db.execute("SELECT 1 FROM users WHERE email = ?", (dados.email,)).fetchone():
        raise HTTPException(409, "email_ja_cadastrado")
    cur = db.execute(
        "INSERT INTO users (email, senha_hash, criado_em) VALUES (?, ?, ?)",
        (dados.email, _hasher.hash(dados.senha), agora.isoformat()),
    )
    _abrir_sessao(response, settings, cur.lastrowid)
    return {"email": dados.email}


@router.post("/auth/login")
def login(dados: LoginIn, request: Request, response: Response, db: Db) -> dict:
    settings: Settings = request.app.state.settings
    limiter: LoginLimiter = request.app.state.login_limiter
    ip, agora = _ip(request), datetime.now(UTC)
    if limiter.bloqueado(ip, agora):
        raise HTTPException(429, "muitas_tentativas")
    row = db.execute("SELECT id, senha_hash FROM users WHERE email = ?", (dados.email,)).fetchone()
    try:
        ok = row is not None and _hasher.verify(row["senha_hash"], dados.senha)
    except (VerificationError, InvalidHashError):
        ok = False
    if not ok:
        limiter.falhou(ip, agora)
        raise HTTPException(401, "credenciais_invalidas")
    limiter.acertou(ip)
    _abrir_sessao(response, settings, row["id"])
    return {"email": dados.email}


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


@router.get("/me")
def me(user_id: UserId, db: Db) -> dict:
    email = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()["email"]
    perfil = db.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    return {"email": email, "perfil_completo": perfil is not None}
