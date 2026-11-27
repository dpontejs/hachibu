"""Memórias do aluno: fatos estáveis que o coach precisa lembrar entre conversas.

Três tipos: restrição (alimentar ou de saúde), condição física e gosto. O aluno vê e edita tudo pelas rotas;
o coach grava pelas tools, mas só pode apagar gostos (restrição e condição só o aluno remove).
"""

import sqlite3
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from hachibu.auth import UserId
from hachibu.db import Db

Tipo = Literal["restricao", "condicao", "gosto"]
Origem = Literal["coach", "aluno"]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
LIMITE = 60
ORDEM = {"restricao": 0, "condicao": 1, "gosto": 2}

router = APIRouter(prefix="/api/memorias")


class MemoriaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Tipo
    texto: Texto


class TextoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: Texto


class MemoriaOut(BaseModel):
    id: int
    tipo: Tipo
    texto: str
    origem: Origem
    criado_em: str


class LimiteDeMemorias(Exception):
    pass


class MemoriaRepetida(Exception):
    pass


def normalizar(texto: str) -> str:
    return " ".join(texto.lower().split())


def _ler(db, user_id: int, id_: int) -> MemoriaOut | None:
    row = db.execute(
        "SELECT id, tipo, texto, origem, criado_em FROM memorias WHERE id = ? AND user_id = ?", (id_, user_id)
    ).fetchone()
    return MemoriaOut(**dict(row)) if row else None


def listar(db, user_id: int) -> list[MemoriaOut]:
    """Restrições, depois condições, depois gostos; dentro de cada tipo, as mais antigas primeiro."""
    rows = db.execute(
        "SELECT id, tipo, texto, origem, criado_em FROM memorias WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return sorted((MemoriaOut(**dict(r)) for r in rows), key=lambda m: ORDEM[m.tipo])


def criar(db, user_id: int, tipo: str, texto: str, origem: str) -> tuple[MemoriaOut, bool]:
    """Devolve (memória, criada?). Repetida (mesmo tipo e texto normalizado) devolve a existente."""
    texto = " ".join(texto.split())
    existente = db.execute(
        "SELECT id FROM memorias WHERE user_id = ? AND tipo = ? AND texto_normalizado = ?",
        (user_id, tipo, normalizar(texto)),
    ).fetchone()
    if existente:
        return _ler(db, user_id, existente["id"]), False
    total = db.execute("SELECT COUNT(*) AS n FROM memorias WHERE user_id = ?", (user_id,)).fetchone()["n"]
    if total >= LIMITE:
        raise LimiteDeMemorias
    cur = db.execute(
        "INSERT INTO memorias (user_id, tipo, texto, texto_normalizado, origem, criado_em) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, tipo, texto, normalizar(texto), origem, datetime.now(UTC).isoformat()),
    )
    return _ler(db, user_id, cur.lastrowid), True


def editar(db, user_id: int, id_: int, texto: str) -> MemoriaOut | None:
    texto = " ".join(texto.split())
    try:
        cur = db.execute(
            "UPDATE memorias SET texto = ?, texto_normalizado = ? WHERE id = ? AND user_id = ?",
            (texto, normalizar(texto), id_, user_id),
        )
    except sqlite3.IntegrityError:
        raise MemoriaRepetida from None
    return _ler(db, user_id, id_) if cur.rowcount else None


def apagar(db, user_id: int, id_: int, so_gostos: bool = False) -> MemoriaOut | None:
    """Apaga e devolve a memória apagada; None se não existe (ou não é do usuário, ou não é gosto)."""
    memoria = _ler(db, user_id, id_)
    if memoria is None or (so_gostos and memoria.tipo != "gosto"):
        return None
    db.execute("DELETE FROM memorias WHERE id = ? AND user_id = ?", (id_, user_id))
    return memoria


@router.get("")
def rota_listar(user_id: UserId, db: Db) -> dict:
    return {"memorias": [m.model_dump() for m in listar(db, user_id)]}


@router.post("", status_code=201)
def rota_criar(dados: MemoriaIn, response: Response, user_id: UserId, db: Db) -> MemoriaOut:
    try:
        memoria, criada = criar(db, user_id, dados.tipo, dados.texto, "aluno")
    except LimiteDeMemorias:
        raise HTTPException(409, "limite_de_memorias") from None
    if not criada:
        response.status_code = 200
    return memoria


@router.patch("/{id_}")
def rota_editar(id_: int, dados: TextoIn, user_id: UserId, db: Db) -> MemoriaOut:
    try:
        memoria = editar(db, user_id, id_, dados.texto)
    except MemoriaRepetida:
        raise HTTPException(409, "memoria_repetida") from None
    if memoria is None:
        raise HTTPException(404, "memoria_inexistente")
    return memoria


@router.delete("/{id_}", status_code=204)
def rota_apagar(id_: int, user_id: UserId, db: Db) -> Response:
    if apagar(db, user_id, id_) is None:
        raise HTTPException(404, "memoria_inexistente")
    return Response(status_code=204)
