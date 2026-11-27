"""Diário do dia: refeições, água e o saldo contra as metas."""

from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from hachibu.auth import UserId
from hachibu.db import Db
from hachibu.perfil import ler_metas

router = APIRouter(prefix="/api")


class RefeicaoManualIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=120)
    kcal: float = Field(ge=0, le=5000)
    proteina_g: float = Field(ge=0, le=500)
    carbo_g: float = Field(ge=0, le=1000)
    gordura_g: float = Field(ge=0, le=500)


class ItemTacoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alimento_id: int
    gramas: float = Field(gt=0, le=2000)


class RefeicaoTacoIn(BaseModel):
    """Refeição montada com alimentos da TACO: os macros são calculados aqui, nunca vêm do cliente."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=120)
    itens: list[ItemTacoIn] = Field(min_length=1, max_length=30)


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


MACROS = ("kcal", "proteina_g", "carbo_g", "gordura_g")

# A presença de "itens" decide o formato. Sem isso, um corpo com itens e macros virava refeição manual
# (itens descartados, kcal do cliente gravado), e os erros de validação misturavam os dois formatos.
RefeicaoIn = Annotated[
    Annotated[RefeicaoTacoIn, Tag("taco")] | Annotated[RefeicaoManualIn, Tag("manual")],
    Discriminator(lambda v: "taco" if isinstance(v, dict) and "itens" in v else "manual"),
]


class AlimentoInexistente(ValueError):
    def __init__(self, alimento_id: int):
        super().__init__(f"alimento {alimento_id} não existe na TACO")
        self.alimento_id = alimento_id


def itens_da_taco(db, itens: list[tuple[int, float]]) -> list[dict]:
    """Calcula cada item (alimento_id, gramas) a partir da TACO. Os macros nunca vêm de fora."""
    calculados = []
    for alimento_id, gramas in itens:
        alimento = db.execute(
            "SELECT id, nome, kcal, proteina_g, carbo_g, gordura_g FROM foods WHERE id = ?", (alimento_id,)
        ).fetchone()
        if alimento is None:
            raise AlimentoInexistente(alimento_id)
        fator = gramas / 100
        calculados.append(
            {"food_id": alimento["id"], "nome": alimento["nome"], "gramas": gramas}
            | {m: alimento[m] * fator for m in MACROS}
        )
    return calculados


def gravar_refeicao(
    db, user_id: int, dia: str, criado_em: str, nome: str, itens: list[dict], totais: dict, fonte: str
) -> int:
    db.execute("BEGIN")
    cur = db.execute(
        "INSERT INTO meals (user_id, data, criado_em, nome, kcal, proteina_g, carbo_g, gordura_g, fonte) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, dia, criado_em, nome, *(totais[m] for m in MACROS), fonte),
    )
    db.executemany(
        "INSERT INTO meal_items (meal_id, food_id, nome, gramas, kcal, proteina_g, carbo_g, gordura_g) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(cur.lastrowid, i["food_id"], i["nome"], i["gramas"], *(i[m] for m in MACROS)) for i in itens],
    )
    db.execute("COMMIT")
    return cur.lastrowid


def gravar_agua(db, user_id: int, dia: str, criado_em: str, ml: int) -> int:
    cur = db.execute(
        "INSERT INTO water_logs (user_id, data, criado_em, ml) VALUES (?, ?, ?, ?)",
        (user_id, dia, criado_em, ml),
    )
    return cur.lastrowid


@router.post("/refeicoes", status_code=201)
def registrar_refeicao(dados: RefeicaoIn, user_id: UserId, request: Request, db: Db) -> dict:
    if isinstance(dados, RefeicaoTacoIn):
        try:
            itens = itens_da_taco(db, [(i.alimento_id, i.gramas) for i in dados.itens])
        except AlimentoInexistente:
            raise HTTPException(422, "alimento_inexistente") from None
        totais = {m: sum(i[m] for i in itens) for m in MACROS}
        fonte = "taco"
    else:
        itens = []
        totais = {m: getattr(dados, m) for m in MACROS}
        fonte = "manual"
    meal_id = gravar_refeicao(
        db, user_id, _hoje(request), _agora(request).isoformat(), dados.nome, itens, totais, fonte
    )
    return {"id": meal_id}


@router.post("/agua", status_code=201)
def registrar_agua(dados: AguaIn, user_id: UserId, request: Request, db: Db) -> dict:
    return {"id": gravar_agua(db, user_id, _hoje(request), _agora(request).isoformat(), dados.ml)}


@router.get("/hoje")
def obter_hoje(user_id: UserId, request: Request, db: Db) -> dict:
    resumo = resumo_do_dia(db, user_id, _hoje(request))
    if resumo is None:
        raise HTTPException(409, "perfil_incompleto")
    return resumo


def resumo_do_dia(db, user_id: int, dia: str) -> dict | None:
    """Metas, consumido, água e refeições do dia; None se o usuário ainda não tem perfil."""
    metas = ler_metas(db, user_id)
    if metas is None:
        return None
    refeicoes = db.execute(
        "SELECT id, nome, kcal, proteina_g, carbo_g, gordura_g, criado_em FROM meals "
        "WHERE user_id = ? AND data = ? ORDER BY criado_em, id",
        (user_id, dia),
    ).fetchall()
    agua = db.execute(
        "SELECT COALESCE(SUM(ml), 0) AS total FROM water_logs WHERE user_id = ? AND data = ?", (user_id, dia)
    ).fetchone()["total"]
    itens_por_refeicao: dict[int, list[dict]] = {}
    for i in db.execute(
        "SELECT mi.meal_id, mi.nome, mi.gramas, mi.kcal FROM meal_items mi JOIN meals m ON m.id = mi.meal_id "
        "WHERE m.user_id = ? AND m.data = ? ORDER BY mi.id",
        (user_id, dia),
    ):
        itens_por_refeicao.setdefault(i["meal_id"], []).append(
            {"nome": i["nome"], "gramas": i["gramas"], "kcal": round(i["kcal"], 1)}
        )
    consumido = {campo: round(sum(r[campo] for r in refeicoes), 1) for campo in MACROS}
    return {
        "data": dia,
        "metas": metas.model_dump(),
        "consumido": consumido,
        "agua_ml": agua,
        "refeicoes": [
            {
                "id": r["id"],
                "nome": r["nome"],
                "kcal": round(r["kcal"], 1),
                "criado_em": r["criado_em"],
                "itens": itens_por_refeicao.get(r["id"], []),
            }
            for r in refeicoes
        ],
    }
