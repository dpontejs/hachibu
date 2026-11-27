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
from hachibu.coach.agente import AprovacaoPendente, RespostaCoach, historico, primeira_fala, responder
from hachibu.coach.foto import TAMANHO_MAXIMO, validar_foto
from hachibu.db import Db
from hachibu.diario import hoje

router = APIRouter(prefix="/api/coach")
log = logging.getLogger("hachibu.coach")
TAMANHO_TITULO = 60
LIMITE_CONVERSAS = 50


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


def titulo_de(fala: str) -> str:
    """Começo da primeira fala, numa linha só, cortado em 60 caracteres."""
    texto = " ".join(fala.split())
    return texto if len(texto) <= TAMANHO_TITULO else texto[: TAMANHO_TITULO - 1].rstrip() + "…"


def _registrar(db, user_id: int, thread_id: str, nova: bool, mensagem: str, r: RespostaCoach) -> None:
    """Grava a conversa no índice só depois que o coach respondeu: falha não cria nem reordena conversa."""
    agora = datetime.now(UTC).isoformat()
    pendente = int(r.pendente is not None)
    if nova:
        db.execute(
            "INSERT INTO coach_threads (thread_id, user_id, criado_em, atualizado_em, titulo, pendente) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (thread_id, user_id, agora, agora, titulo_de(mensagem), pendente),
        )
    else:
        db.execute(
            "UPDATE coach_threads SET atualizado_em = ?, pendente = ? WHERE thread_id = ?",
            (agora, pendente, thread_id),
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
    except AprovacaoPendente:
        raise HTTPException(409, "aprovacao_pendente") from None
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
        # Recusa antes de carregar tudo na memória: o upload não tem limite no multipart.
        if foto.size is not None and foto.size > TAMANHO_MAXIMO:
            raise HTTPException(422, "foto maior que 5 MB")
        conteudo = await foto.read(TAMANHO_MAXIMO + 1)
        try:
            validar_foto(conteudo, foto.content_type or "")
        except ValueError as e:
            raise HTTPException(422, str(e)) from None
        anexo = (conteudo, foto.content_type)
    _contar_uso(db, request, user_id)
    nova = not thread_id
    thread_id = thread_id or uuid.uuid4().hex
    settings = request.app.state.settings
    # O agente é síncrono e a chamada ao modelo leva segundos: fora do event loop.
    r = await run_in_threadpool(
        _chamar, responder, settings, modelo, user_id, thread_id, mensagem=mensagem, foto=anexo
    )
    _registrar(db, user_id, thread_id, nova, mensagem, r)
    return _saida(thread_id, r)


@router.post("/{thread_id}/decisao")
def decidir(thread_id: str, dados: DecisaoIn, request: Request, user_id: UserId, db: Db) -> dict:
    modelo = _modelo(request)
    _exigir_dono(db, user_id, thread_id)
    settings = request.app.state.settings
    if historico(settings, modelo, user_id, thread_id).pendente is None:
        raise HTTPException(409, "nada_para_decidir")
    decisao = {"aprovar": dados.aprovar, "motivo": dados.motivo}
    r = _chamar(responder, settings, modelo, user_id, thread_id, decisao=decisao)
    _registrar(db, user_id, thread_id, False, "", r)
    return _saida(thread_id, r)


# Declarada antes de /{thread_id}: senão "conversas" seria lido como o id de uma thread.
@router.get("/conversas")
def listar(request: Request, user_id: UserId, db: Db) -> dict:
    """Leitura local: não depende do modelo nem monta o agente."""
    linhas = db.execute(
        "SELECT thread_id, titulo, criado_em, atualizado_em, pendente FROM coach_threads WHERE user_id = ? "
        "ORDER BY atualizado_em DESC, criado_em DESC LIMIT ?",
        (user_id, LIMITE_CONVERSAS),
    ).fetchall()
    saida = []
    for r in linhas:
        titulo = r["titulo"]
        if not titulo:
            # Conversa de antes da lista existir: o título sai da primeira fala salva, uma vez só.
            fala = primeira_fala(request.app.state.settings, r["thread_id"])
            if fala is None:
                continue  # nada salvo: não há o que reabrir
            titulo = titulo_de(fala)
            db.execute("UPDATE coach_threads SET titulo = ? WHERE thread_id = ?", (titulo, r["thread_id"]))
        saida.append(
            {
                "thread_id": r["thread_id"],
                "titulo": titulo,
                "criado_em": r["criado_em"],
                "atualizado_em": r["atualizado_em"],
                "pendente": bool(r["pendente"]),
            }
        )
    return {"conversas": saida}


@router.get("/{thread_id}")
def obter(thread_id: str, request: Request, user_id: UserId, db: Db) -> dict:
    modelo = _modelo(request)
    _exigir_dono(db, user_id, thread_id)
    return _saida(thread_id, historico(request.app.state.settings, modelo, user_id, thread_id))
