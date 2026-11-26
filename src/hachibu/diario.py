"""Diário do dia: refeições, água e o saldo contra as metas."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from hachibu.auth import UserId
from hachibu.db import Db
from hachibu.perfil import ler_metas

router = APIRouter(prefix="/api")


class RefeicaoManualIn(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    kcal: float = Field(ge=0, le=5000)
    proteina_g: float = Field(ge=0, le=500)
    carbo_g: float = Field(ge=0, le=1000)
    gordura_g: float = Field(ge=0, le=500)


class AguaIn(BaseModel):
    ml: int = Field(ge=1, le=2000)


def hoje(tz: str, agora: datetime | None = None) -> date:
    """A data local do usuário (o dia vira à meia-noite de Brasília, não de UTC)."""
    return (agora or datetime.now(UTC)).astimezone(ZoneInfo(tz)).date()


def _agora(request: Request) -> datetime:
    relogio = getattr(request.app.state, "agora", None)
    return relogio() if relogio else datetime.now(UTC)


def _hoje(request: Request) -> str:
    return hoje(request.app.state.settings.app_tz, _agora(request)).isoformat()


@router.post("/refeicoes", status_code=201)
def registrar_refeicao(dados: RefeicaoManualIn, user_id: UserId, request: Request, db: Db) -> dict:
    cur = db.execute(
        "INSERT INTO meals (user_id, data, criado_em, nome, kcal, proteina_g, carbo_g, gordura_g, fonte) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual')",
        (
            user_id,
            _hoje(request),
            _agora(request).isoformat(),
            dados.nome,
            dados.kcal,
            dados.proteina_g,
            dados.carbo_g,
            dados.gordura_g,
        ),
    )
    return {"id": cur.lastrowid}


@router.post("/agua", status_code=201)
def registrar_agua(dados: AguaIn, user_id: UserId, request: Request, db: Db) -> dict:
    cur = db.execute(
        "INSERT INTO water_logs (user_id, data, criado_em, ml) VALUES (?, ?, ?, ?)",
        (user_id, _hoje(request), _agora(request).isoformat(), dados.ml),
    )
    return {"id": cur.lastrowid}


@router.get("/hoje")
def obter_hoje(user_id: UserId, request: Request, db: Db) -> dict:
    metas = ler_metas(db, user_id)
    if metas is None:
        raise HTTPException(409, "perfil_incompleto")
    dia = _hoje(request)
    refeicoes = db.execute(
        "SELECT id, nome, kcal, proteina_g, carbo_g, gordura_g, criado_em FROM meals "
        "WHERE user_id = ? AND data = ? ORDER BY criado_em, id",
        (user_id, dia),
    ).fetchall()
    agua = db.execute(
        "SELECT COALESCE(SUM(ml), 0) AS total FROM water_logs WHERE user_id = ? AND data = ?", (user_id, dia)
    ).fetchone()["total"]
    consumido = {
        campo: round(sum(r[campo] for r in refeicoes), 1)
        for campo in ("kcal", "proteina_g", "carbo_g", "gordura_g")
    }
    return {
        "data": dia,
        "metas": metas.model_dump(),
        "consumido": consumido,
        "agua_ml": agua,
        "refeicoes": [
            {"id": r["id"], "nome": r["nome"], "kcal": r["kcal"], "criado_em": r["criado_em"]}
            for r in refeicoes
        ],
    }
