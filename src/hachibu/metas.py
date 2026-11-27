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
    # Meta prescrita por nutricionista: quando existe, substitui a fórmula (quem examinou sabe mais).
    meta_profissional_kcal: int | None = Field(default=None, ge=1000, le=5000)
    meta_profissional_proteina_g: int | None = Field(default=None, ge=0, le=500)
    meta_profissional_carbo_g: int | None = Field(default=None, ge=0, le=1000)
    meta_profissional_gordura_g: int | None = Field(default=None, ge=0, le=300)
    # Corrida (opcionais): o nível pode ser diferente do da musculação. Vazio = iniciante, automático, 3.
    nivel_corrida: Literal["iniciante", "intermediario", "avancado"] | None = None
    corrida_quando: Literal["automatico", "mesmo_dia", "dias_separados"] | None = None
    corridas_semana: int | None = Field(default=None, ge=1, le=7)


class Metas(BaseModel):
    kcal: int
    proteina_g: int
    carbo_g: int
    gordura_g: int
    agua_ml: int
    origem: Literal["formula", "profissional", "coach"] = "formula"


class Diagnostico(BaseModel):
    tmb: int
    formula: Literal["mifflin-st-jeor", "katch-mcardle"]
    fator_atividade: float
    gasto_diario: int
    # Diferença em kcal entre a meta e o gasto diário: negativo é déficit, positivo é superávit.
    ajuste_objetivo: int
    relacao_cintura_altura: float | None
    alerta_cintura: bool
    abaixo_do_piso: bool
    metas: Metas


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


def gasto_diario(p: PerfilIn) -> float:
    return taxa_metabolica_basal(p) * _fator_atividade(p.dias_semana)


def calcular_metas(p: PerfilIn) -> Metas:
    proteina = PROTEINA_G_POR_KG[p.objetivo] * p.peso_kg
    gordura = GORDURA_G_POR_KG * p.peso_kg
    agua = round(AGUA_ML_POR_KG * p.peso_kg)
    if p.meta_profissional_kcal is not None:
        kcal = p.meta_profissional_kcal
        proteina = p.meta_profissional_proteina_g if p.meta_profissional_proteina_g is not None else proteina
        gordura = p.meta_profissional_gordura_g if p.meta_profissional_gordura_g is not None else gordura
        carbo = p.meta_profissional_carbo_g
        if carbo is None:
            carbo = max((kcal - 4 * proteina - 9 * gordura) / 4, 0)
        origem = "profissional"
    else:
        kcal = max(gasto_diario(p) * FATOR_OBJETIVO[p.objetivo], PISO_KCAL[p.sexo])
        carbo = max((kcal - 4 * proteina - 9 * gordura) / 4, 0)
        origem = "formula"
    return Metas(
        kcal=round(kcal),
        proteina_g=round(proteina),
        carbo_g=round(carbo),
        gordura_g=round(gordura),
        agua_ml=agua,
        origem=origem,
    )


def diagnostico(p: PerfilIn) -> Diagnostico:
    metas = calcular_metas(p)
    rca = round(p.cintura_cm / p.altura_cm, 2) if p.cintura_cm else None
    return Diagnostico(
        tmb=round(taxa_metabolica_basal(p)),
        formula="katch-mcardle" if p.percentual_gordura is not None else "mifflin-st-jeor",
        fator_atividade=_fator_atividade(p.dias_semana),
        gasto_diario=round(gasto_diario(p)),
        ajuste_objetivo=metas.kcal - round(gasto_diario(p)),
        relacao_cintura_altura=rca,
        # Cintura/altura >= 0,5 é um marcador conhecido de gordura abdominal.
        alerta_cintura=rca is not None and rca >= 0.5,
        abaixo_do_piso=metas.kcal < PISO_KCAL[p.sexo],
        metas=metas,
    )
