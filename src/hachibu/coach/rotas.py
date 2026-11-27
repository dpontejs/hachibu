"""Rotas do coach: conversa, decisão sobre propostas e histórico, com dono da thread e cota diária."""

import asyncio
import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hachibu.auth import UserId
from hachibu.coach.agente import (
    AprovacaoPendente,
    RespostaCoach,
    _checkpointer,
    historico,
    primeira_fala,
    responder,
)
from hachibu.coach.foto import TAMANHO_MAXIMO, validar_foto
from hachibu.db import Db, connect
from hachibu.diario import hoje

router = APIRouter(prefix="/api/coach")
log = logging.getLogger("hachibu.coach")
BATIDA_S = 15  # comentário SSE de tempos em tempos: proxies e o iOS não derrubam a conexão parada
THREAD_ID = re.compile(r"^[0-9a-f]{32}$")
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


_trava = threading.Lock()


def _em_andamento(request: Request) -> set[str]:
    """Threads processando agora neste processo (um worker): o app usa para recuperar a resposta."""
    if not hasattr(request.app.state, "coach_em_andamento"):
        request.app.state.coach_em_andamento = set()
    return request.app.state.coach_em_andamento


def _reservar(request: Request, db, user_id: int, thread_id: str, nova: bool, mensagem: str) -> None:
    """Marca a conversa como em andamento (e cria a linha, se nova) antes de qualquer trabalho.

    Sob trava: duas mensagens na mesma conversa ao mesmo tempo corromperiam o histórico (uma veria as
    chamadas em voo da outra como órfãs). Id novo que já existe no histórico salvo é recusado: o id vem
    do app e não pode reabrir a conversa de outra pessoa.
    """
    with _trava:
        andamento = _em_andamento(request)
        if thread_id in andamento:
            raise HTTPException(409, "em_andamento")
        if nova:
            salvo = _checkpointer(request.app.state.settings).get({"configurable": {"thread_id": thread_id}})
            if salvo is not None:
                raise HTTPException(404, "conversa_inexistente")
            agora = datetime.now(UTC).isoformat()
            try:
                db.execute(
                    "INSERT INTO coach_threads (thread_id, user_id, criado_em, atualizado_em, titulo) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (thread_id, user_id, agora, agora, titulo_de(mensagem)),
                )
            except sqlite3.IntegrityError:
                raise HTTPException(404, "conversa_inexistente") from None
        andamento.add(thread_id)


def _desfazer(request: Request, thread_id: str, nova: bool) -> None:
    """Libera a conversa; se era nova, apaga a linha e o histórico salvo (pode ter dado de saúde)."""
    if nova:
        settings = request.app.state.settings
        db = connect(settings.db_path)
        try:
            db.execute("DELETE FROM coach_threads WHERE thread_id = ?", (thread_id,))
        finally:
            db.close()
        _checkpointer(settings).delete_thread(thread_id)
    _em_andamento(request).discard(thread_id)


def _executar(
    request: Request,
    user_id: int,
    thread_id: str,
    nova: bool,
    funcao_kwargs: dict,
    ao_passo=None,
) -> RespostaCoach:
    """Roda o agente (em thread do pool) com a conversa já reservada; libera no fim.

    Conversa nova que falha é desfeita. O log tem só métricas, nunca o texto (dados de saúde).
    """
    settings = request.app.state.settings
    modelo = request.app.state.modelo_coach
    passos: list[str] = []
    inicio = time.monotonic()
    resultado = "erro"

    def passo(nome: str) -> None:
        passos.append(nome)
        if ao_passo:
            ao_passo(nome)

    try:
        try:
            r = _chamar(
                responder,
                settings,
                modelo,
                user_id,
                thread_id,
                ao_passo=passo,
                **funcao_kwargs,
            )
        except BaseException:
            _desfazer(request, thread_id, nova)
            raise
        db = connect(settings.db_path)
        try:
            db.execute(
                "UPDATE coach_threads SET atualizado_em = ?, pendente = ? WHERE thread_id = ?",
                (datetime.now(UTC).isoformat(), int(r.pendente is not None), thread_id),
            )
        finally:
            db.close()
        _em_andamento(request).discard(thread_id)
        resultado = "pendente" if r.pendente else "ok"
        return r
    finally:
        log.info(
            "coach thread=%s duracao=%.1fs passos=%d ferramentas=%s foto=%s resultado=%s",
            thread_id[:8],
            time.monotonic() - inicio,
            len(passos),
            ",".join(passos) or "-",
            "sim" if funcao_kwargs.get("foto") else "nao",
            resultado,
        )


def _saida(thread_id: str, r: RespostaCoach, processando: bool = False) -> dict:
    return {
        "thread_id": thread_id,
        "processando": processando,
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
    _modelo(request)
    nova = True
    if thread_id:
        if not THREAD_ID.match(thread_id):
            raise HTTPException(422, "thread_id inválido")
        existe = db.execute("SELECT 1 FROM coach_threads WHERE thread_id = ?", (thread_id,)).fetchone()
        if existe:
            _exigir_dono(db, user_id, thread_id)
            nova = False
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
    thread_id = thread_id or uuid.uuid4().hex
    _reservar(request, db, user_id, thread_id, nova, mensagem)
    try:
        _contar_uso(db, request, user_id)
    except BaseException:
        _desfazer(request, thread_id, nova)
        raise
    kwargs = {"mensagem": mensagem, "foto": anexo}
    # O agente é síncrono e a chamada ao modelo leva segundos: fora do event loop. Começa aqui, e não
    # dentro do stream: se o app desconectar antes do primeiro byte, o trabalho segue e fica salvo.
    loop = asyncio.get_running_loop()
    fila: asyncio.Queue[str] = asyncio.Queue()

    def ao_passo(nome: str) -> None:
        loop.call_soon_threadsafe(fila.put_nowait, nome)

    tarefa = asyncio.ensure_future(
        run_in_threadpool(_executar, request, user_id, thread_id, nova, kwargs, ao_passo)
    )
    # Ninguém mais observa a tarefa se o app sair no meio: evita "exception was never retrieved".
    tarefa.add_done_callback(lambda t: t.cancelled() or t.exception())
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(
            _eventos(thread_id, tarefa, fila),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return _saida(thread_id, await tarefa)


def _sse(tipo: str, dado: dict) -> str:
    return f"event: {tipo}\ndata: {json.dumps(dado, ensure_ascii=False)}\n\n"


async def _eventos(thread_id: str, tarefa: asyncio.Future, fila: asyncio.Queue):
    """Passos do agente conforme acontecem, e no fim a mesma saída da rota JSON.

    Se o app desconectar (iOS em segundo plano), o agente continua na thread e grava a resposta: o app a
    recupera pelo histórico.
    """
    pegar: asyncio.Future | None = None
    try:
        while True:
            pegar = asyncio.ensure_future(fila.get())
            feitos, _ = await asyncio.wait(
                {pegar, tarefa}, timeout=BATIDA_S, return_when=asyncio.FIRST_COMPLETED
            )
            if pegar in feitos:
                yield _sse("passo", {"ferramenta": pegar.result()})
                continue
            pegar.cancel()
            if tarefa not in feitos:
                yield ": vivo\n\n"
                continue
            while not fila.empty():
                yield _sse("passo", {"ferramenta": fila.get_nowait()})
            erro = tarefa.exception()
            if isinstance(erro, HTTPException):
                yield _sse("erro", {"status": erro.status_code, "detail": erro.detail})
            elif erro is not None:
                log.error("coach falhou no stream: %s", type(erro).__name__)
                yield _sse("erro", {"status": 500, "detail": "erro_interno"})
            else:
                yield _sse("fim", _saida(thread_id, tarefa.result()))
            return
    finally:
        if pegar is not None and not pegar.done():
            pegar.cancel()


@router.post("/{thread_id}/decisao")
def decidir(thread_id: str, dados: DecisaoIn, request: Request, user_id: UserId, db: Db) -> dict:
    modelo = _modelo(request)
    _exigir_dono(db, user_id, thread_id)
    settings = request.app.state.settings
    if historico(settings, modelo, user_id, thread_id).pendente is None:
        raise HTTPException(409, "nada_para_decidir")
    decisao = {"aprovar": dados.aprovar, "motivo": dados.motivo}
    _reservar(request, db, user_id, thread_id, False, "")
    return _saida(thread_id, _executar(request, user_id, thread_id, False, {"decisao": decisao}))


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
    r = historico(request.app.state.settings, modelo, user_id, thread_id)
    return _saida(thread_id, r, processando=thread_id in _em_andamento(request))
