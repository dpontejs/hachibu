"""Alimentos da TACO (4ª ed., NEPA-UNICAMP 2011): carga no banco e busca sem acento."""

import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

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
