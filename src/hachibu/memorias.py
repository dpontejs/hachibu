"""Memórias do aluno: fatos estáveis que o coach precisa lembrar entre conversas.

Três tipos: restrição (alimentar ou de saúde), condição física e gosto. O aluno vê e edita tudo pelas rotas;
o coach grava pelas tools, mas só pode apagar gostos (restrição e condição só o aluno remove).
"""

import sqlite3
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import AfterValidator, BaseModel, ConfigDict

from hachibu.auth import UserId
from hachibu.db import Db

Tipo = Literal["restricao", "condicao", "gosto"]
Origem = Literal["coach", "aluno"]
# Teto por tipo: muitos gostos nunca impedem gravar uma restrição ou condição.
LIMITES = {"restricao": 30, "condicao": 30, "gosto": 60}
ORDEM = {"restricao": 0, "condicao": 1, "gosto": 2}

router = APIRouter(prefix="/api/memorias")


def limpar(texto: str) -> str:
    """Tira caracteres invisíveis (formatação Unicode), une acentos (NFC) e colapsa espaços e quebras."""
    texto = "".join(c for c in unicodedata.normalize("NFC", texto) if unicodedata.category(c) != "Cf")
    return " ".join(texto.split())


def _validar_texto(texto: str) -> str:
    texto = limpar(texto)
    if not 2 <= len(texto) <= 200 or not any(c.isalnum() for c in texto):
        raise ValueError("a memória precisa ter de 2 a 200 caracteres, com letras ou números")
    return texto


Texto = Annotated[str, AfterValidator(_validar_texto)]


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
    def __init__(self, tipo: str):
        super().__init__(tipo)
        self.tipo = tipo


class MemoriaRepetida(Exception):
    pass


def normalizar(texto: str) -> str:
    """Chave de unicidade: sem acento, sem caixa, sem pontuação final ("Não gosta." = "nao gosta")."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split()).rstrip(" .!;,")


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
    """Devolve (memória, criada?). Repetida (mesmo tipo e texto normalizado) devolve a existente.

    Numa transação IMMEDIATE: o Gemini pode pedir o mesmo lembrar duas vezes em paralelo.
    """
    texto = limpar(texto)
    chave = normalizar(texto)
    db.execute("BEGIN IMMEDIATE")
    try:
        existente = db.execute(
            "SELECT id FROM memorias WHERE user_id = ? AND tipo = ? AND texto_normalizado = ?",
            (user_id, tipo, chave),
        ).fetchone()
        if existente:
            db.execute("COMMIT")
            return _ler(db, user_id, existente["id"]), False
        total = db.execute(
            "SELECT COUNT(*) AS n FROM memorias WHERE user_id = ? AND tipo = ?", (user_id, tipo)
        ).fetchone()["n"]
        if total >= LIMITES[tipo]:
            raise LimiteDeMemorias(tipo)
        cur = db.execute(
            "INSERT INTO memorias (user_id, tipo, texto, texto_normalizado, origem, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, tipo, texto, chave, origem, datetime.now(UTC).isoformat()),
        )
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return _ler(db, user_id, cur.lastrowid), True


def editar(db, user_id: int, id_: int, texto: str) -> MemoriaOut | None:
    texto = limpar(texto)
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
    filtro = " AND tipo = 'gosto'" if so_gostos else ""
    row = db.execute(
        f"DELETE FROM memorias WHERE id = ? AND user_id = ?{filtro} "
        "RETURNING id, tipo, texto, origem, criado_em",
        (id_, user_id),
    ).fetchone()
    return MemoriaOut(**dict(row)) if row else None


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
