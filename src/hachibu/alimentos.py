"""Alimentos da TACO (4ª ed., NEPA-UNICAMP 2011): carga no banco e busca sem acento."""

import csv
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query

from hachibu.auth import UserId
from hachibu.db import Db

TACO_CSV = Path(__file__).parent / "data" / "taco.csv"
VALORES = ("kcal", "proteina_g", "carbo_g", "gordura_g", "fibra_g")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, só letras, dígitos e espaços simples."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).split())


def carregar_taco(conn: sqlite3.Connection) -> int:
    """Insere a TACO se a tabela estiver vazia. Devolve quantos alimentos inseriu."""
    if conn.execute("SELECT 1 FROM foods LIMIT 1").fetchone():
        return 0
    with TACO_CSV.open(encoding="utf-8") as f:
        linhas = [
            (int(r["id"]), r["nome"], normalizar(r["nome"]), r["categoria"], *(float(r[v]) for v in VALORES))
            for r in csv.DictReader(f)
        ]
    conn.execute("BEGIN")
    conn.executemany(
        "INSERT INTO foods (id, nome, nome_busca, categoria, kcal, proteina_g, carbo_g, gordura_g, fibra_g) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        linhas,
    )
    conn.execute("COMMIT")
    return len(linhas)


def buscar_alimentos(conn: sqlite3.Connection, q: str, limite: int = 20) -> list[dict]:
    """Todos os termos precisam aparecer no nome.

    Ordem: quem começa pelo 1º termo, depois o nome mais curto.
    """
    termos = normalizar(q).split()
    if not termos:
        return []
    filtros = " AND ".join("nome_busca LIKE ?" for _ in termos)
    linhas = conn.execute(
        f"SELECT id, nome, categoria, kcal, proteina_g, carbo_g, gordura_g FROM foods WHERE {filtros} "
        "ORDER BY nome_busca NOT LIKE ?, length(nome_busca), nome_busca LIMIT ?",
        (*(f"%{t}%" for t in termos), f"{termos[0]}%", limite),
    ).fetchall()
    return [dict(r) for r in linhas]


router = APIRouter(prefix="/api")


@router.get("/alimentos")
def rota_buscar(user_id: UserId, db: Db, q: Annotated[str, Query(min_length=2, max_length=60)]) -> list[dict]:
    return buscar_alimentos(db, q)
