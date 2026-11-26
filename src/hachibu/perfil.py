"""Rotas do perfil: gravar o perfil recalcula e grava as metas."""

from fastapi import APIRouter, HTTPException

from hachibu.auth import UserId
from hachibu.db import Db
from hachibu.metas import Metas, PerfilIn, calcular_metas

router = APIRouter(prefix="/api")

CAMPOS = list(PerfilIn.model_fields)


def ler_metas(db, user_id: int) -> Metas | None:
    row = db.execute(
        "SELECT kcal, proteina_g, carbo_g, gordura_g, agua_ml FROM goals WHERE user_id = ?", (user_id,)
    ).fetchone()
    return Metas(**dict(row)) if row else None


@router.put("/perfil")
def salvar_perfil(perfil: PerfilIn, user_id: UserId, db: Db) -> dict:
    metas = calcular_metas(perfil)
    colunas = ", ".join(CAMPOS)
    marcadores = ", ".join("?" for _ in CAMPOS)
    atualizar = ", ".join(f"{c} = excluded.{c}" for c in CAMPOS)
    db.execute("BEGIN")
    db.execute(
        f"INSERT INTO profiles (user_id, {colunas}) VALUES (?, {marcadores}) "
        f"ON CONFLICT(user_id) DO UPDATE SET {atualizar}",
        (user_id, *(getattr(perfil, c) for c in CAMPOS)),
    )
    db.execute(
        "INSERT INTO goals (user_id, kcal, proteina_g, carbo_g, gordura_g, agua_ml) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET kcal = excluded.kcal, proteina_g = excluded.proteina_g, "
        "carbo_g = excluded.carbo_g, gordura_g = excluded.gordura_g, agua_ml = excluded.agua_ml",
        (user_id, metas.kcal, metas.proteina_g, metas.carbo_g, metas.gordura_g, metas.agua_ml),
    )
    db.execute("COMMIT")
    return {"perfil": perfil.model_dump(), "metas": metas.model_dump()}


@router.get("/perfil")
def obter_perfil(user_id: UserId, db: Db) -> dict:
    row = db.execute(f"SELECT {', '.join(CAMPOS)} FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "perfil_inexistente")
    return {"perfil": dict(row), "metas": ler_metas(db, user_id).model_dump()}
