"""Versões do plano e progressão da corrida no SQLite.

Cada versão é uma foto imutável do plano (JSON). O histórico de treinos aponta para ela, por isso uma versão
nova nunca apaga a anterior: só deixa de ser a ativa.
"""

from datetime import UTC, datetime

from hachibu.treino.modelos import PlanoIn


def plano_ativo(db, user_id: int) -> tuple[dict, PlanoIn] | None:
    row = db.execute(
        "SELECT id, versao, origem, dados, criado_em FROM planos WHERE user_id = ? AND ativo = 1", (user_id,)
    ).fetchone()
    if row is None:
        return None
    meta = {"id": row["id"], "versao": row["versao"], "origem": row["origem"], "criado_em": row["criado_em"]}
    return meta, PlanoIn.model_validate_json(row["dados"])


def gravar_plano(db, user_id: int, plano: PlanoIn, origem: str) -> int:
    """Grava uma versão nova e a torna ativa, numa transação só. Devolve o número da versão."""
    db.execute("BEGIN IMMEDIATE")
    try:
        ultima = db.execute("SELECT MAX(versao) AS v FROM planos WHERE user_id = ?", (user_id,)).fetchone()[
            "v"
        ]
        versao = (ultima or 0) + 1
        db.execute("UPDATE planos SET ativo = 0 WHERE user_id = ?", (user_id,))
        db.execute(
            "INSERT INTO planos (user_id, versao, origem, dados, criado_em, ativo) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, versao, origem, plano.model_dump_json(), datetime.now(UTC).isoformat()),
        )
        db.execute(
            "INSERT INTO progressao_corrida (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (user_id,)
        )
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return versao


def semana_corrida(db, user_id: int) -> int:
    row = db.execute("SELECT semana FROM progressao_corrida WHERE user_id = ?", (user_id,)).fetchone()
    return row["semana"] if row else 1
