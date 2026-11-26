"""Perfil do aluno e metas diárias por fórmula fixa, sem LLM (previsíveis e testáveis)."""

from typing import Literal

from pydantic import BaseModel, Field

FATOR_OBJETIVO = {"perder": 0.80, "manter": 1.00, "ganhar": 1.10}
PROTEINA_G_POR_KG = {"perder": 2.2, "manter": 1.8, "ganhar": 2.0}
GORDURA_G_POR_KG = 0.8
AGUA_ML_POR_KG = 35
PISO_KCAL = {"M": 1500, "F": 1200}


class PerfilIn(BaseModel):
    sexo: Literal["M", "F"]
    idade: int = Field(ge=14, le=90)
    altura_cm: float = Field(ge=120, le=230)
    peso_kg: float = Field(ge=30, le=250)
    objetivo: Literal["perder", "manter", "ganhar"]
    nivel: Literal["iniciante", "intermediario", "avancado"]
    dias_semana: int = Field(ge=1, le=7)
    minutos_sessao: int = Field(ge=15, le=180)
    equipamento: Literal["academia", "casa_halteres", "peso_corporal"]
    # Opcionais. condicoes_saude é dado sensível: nunca vai para logs.
    percentual_gordura: float | None = Field(default=None, ge=3, le=60)
    cintura_cm: float | None = Field(default=None, ge=40, le=200)
    condicoes_saude: str | None = Field(default=None, max_length=500)


class Metas(BaseModel):
    kcal: int
    proteina_g: int
    carbo_g: int
    gordura_g: int
    agua_ml: int


def _fator_atividade(dias: int) -> float:
    if dias <= 2:
        return 1.375
    if dias <= 4:
        return 1.55
    return 1.725


def taxa_metabolica_basal(p: PerfilIn) -> float:
    if p.percentual_gordura is not None:
        # Katch-McArdle: usa a massa magra, mais precisa quando a composição corporal é conhecida.
        massa_magra = p.peso_kg * (1 - p.percentual_gordura / 100)
        return 370 + 21.6 * massa_magra
    # Mifflin-St Jeor.
    return 10 * p.peso_kg + 6.25 * p.altura_cm - 5 * p.idade + (5 if p.sexo == "M" else -161)


def calcular_metas(p: PerfilIn) -> Metas:
    kcal = taxa_metabolica_basal(p) * _fator_atividade(p.dias_semana) * FATOR_OBJETIVO[p.objetivo]
    kcal = max(kcal, PISO_KCAL[p.sexo])
    proteina = PROTEINA_G_POR_KG[p.objetivo] * p.peso_kg
    gordura = GORDURA_G_POR_KG * p.peso_kg
    carbo = max((kcal - 4 * proteina - 9 * gordura) / 4, 0)
    return Metas(
        kcal=round(kcal),
        proteina_g=round(proteina),
        carbo_g=round(carbo),
        gordura_g=round(gordura),
        agua_ml=round(AGUA_ML_POR_KG * p.peso_kg),
    )
