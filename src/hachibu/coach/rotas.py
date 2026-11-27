"""Rotas do coach: conversa, decisão sobre propostas e histórico, com dono da thread e cota diária."""

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from hachibu.auth import UserId
from hachibu.coach.agente import RespostaCoach, historico, responder
from hachibu.coach.foto import validar_foto
from hachibu.db import Db
from hachibu.diario import hoje

router = APIRouter(prefix="/api/coach")
log = logging.getLogger("hachibu.coach")


class DecisaoIn(BaseModel):
    aprovar: bool
    motivo: str | None = Field(default=None, max_length=300)


def _modelo(request: Request):
    modelo = getattr(request.app.state, "modelo_coach", None)
    if modelo is None:
        raise HTTPException(503, "coach_indisponivel")
    return modelo


def _exigir_dono(db, user_id: int, thread_id: str) -> None:
    dono = db.execute("SELECT user_id FROM coach_threads WHERE thread_id = ?", (thread_id,)).fetchone()
    if dono is None or dono["user_id"] != user_id:
        raise HTTPException(404, "conversa_inexistente")


def _contar_uso(db, request: Request, user_id: int) -> None:
    settings = request.app.state.settings
    dia = hoje(settings.app_tz).isoformat()
    usadas = db.execute(
        "SELECT mensagens FROM coach_uso WHERE user_id = ? AND data = ?", (user_id, dia)
    ).fetchone()
    if usadas and usadas["mensagens"] >= settings.coach_limite_diario:
        raise HTTPException(429, "cota_do_coach")
    db.execute(
        "INSERT INTO coach_uso (user_id, data, mensagens) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, data) DO UPDATE SET mensagens = mensagens + 1",
        (user_id, dia),
    )


def _saida(thread_id: str, r: RespostaCoach) -> dict:
    return {
        "thread_id": thread_id,
        "mensagens": [asdict(m) for m in r.mensagens],
        "pendente": asdict(r.pendente) if r.pendente else None,
    }


def _chamar(funcao, *args, **kwargs) -> RespostaCoach:
    try:
        return funcao(*args, **kwargs)
    except HTTPException:
        raise
    except Exception:
        # Falha do provedor (chave inválida, fora do ar, cota): o resto do app segue funcionando.
        log.exception("coach falhou")
        raise HTTPException(503, "coach_indisponivel") from None


@router.post("")
async def conversar(
    request: Request,
    user_id: UserId,
    db: Db,
    mensagem: Annotated[str, Form(min_length=1, max_length=2000)],
    thread_id: Annotated[str | None, Form(max_length=64)] = None,
    foto: UploadFile | None = None,
) -> dict:
    modelo = _modelo(request)
    if thread_id:
        _exigir_dono(db, user_id, thread_id)
    anexo = None
    if foto is not None:
        conteudo = await foto.read()
        try:
            validar_foto(conteudo, foto.content_type or "")
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        anexo = (conteudo, foto.content_type)
    _contar_uso(db, request, user_id)
    if not thread_id:
        thread_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO coach_threads (thread_id, user_id, criado_em) VALUES (?, ?, ?)",
            (thread_id, user_id, datetime.now(UTC).isoformat()),
        )
    settings = request.app.state.settings
    # O agente é síncrono e a chamada ao modelo leva segundos: fora do event loop.
    r = await run_in_threadpool(
        _chamar, responder, settings, modelo, user_id, thread_id, mensagem=mensagem, foto=anexo
    )
    return _saida(thread_id, r)


@router.post("/{thread_id}/decisao")
def decidir(thread_id: str, dados: DecisaoIn, request: Request, user_id: UserId, db: Db) -> dict:
    modelo = _modelo(request)
    _exigir_dono(db, user_id, thread_id)
    settings = request.app.state.settings
    if historico(settings, modelo, user_id, thread_id).pendente is None:
        raise HTTPException(409, "nada_para_decidir")
    decisao = {"aprovar": dados.aprovar, "motivo": dados.motivo}
    return _saida(thread_id, _chamar(responder, settings, modelo, user_id, thread_id, decisao=decisao))


@router.get("/{thread_id}")
def obter(thread_id: str, request: Request, user_id: UserId, db: Db) -> dict:
    modelo = _modelo(request)
    _exigir_dono(db, user_id, thread_id)
    return _saida(thread_id, historico(request.app.state.settings, modelo, user_id, thread_id))
