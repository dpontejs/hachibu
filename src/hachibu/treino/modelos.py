"""Formato do plano semanal: o mesmo para o plano base, a proposta do coach e a versão gravada."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExercicioPlano(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercicio_id: str
    series: int = Field(ge=1, le=10)
    reps_min: int = Field(ge=1, le=30)
    reps_max: int = Field(ge=1, le=30)
    descanso_s: int = Field(default=90, ge=15, le=600)

    @model_validator(mode="after")
    def _faixa(self):
        if self.reps_max < self.reps_min:
            raise ValueError("reps_max menor que reps_min")
        return self


class CorridaPlano(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # True: o treino vem da semana atual da progressão de iniciante (o plano guarda só a marcação).
    progressao: bool = False
    # recuperacao: caminhada leve ou mobilidade (esforço 1–3); conta como dia sem treino pesado.
    tipo: Literal["corrida_caminhada", "leve", "intervalado", "longao", "recuperacao"]
    duracao_min: int = Field(ge=5, le=240)
    corre_min: float | None = Field(default=None, gt=0, le=240)
    anda_min: float | None = Field(default=None, ge=0, le=30)
    repeticoes: int | None = Field(default=None, ge=1, le=30)
    esforco_alvo: str = Field(max_length=10)


class DiaPlano(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dia: int = Field(ge=0, le=6)  # 0 = segunda
    nome: str = Field(max_length=40)
    exercicios: list[ExercicioPlano] = Field(default_factory=list, max_length=15)
    corrida: CorridaPlano | None = None


class PlanoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dias: list[DiaPlano] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def _sete_dias(self):
        if sorted(d.dia for d in self.dias) != list(range(7)):
            raise ValueError("o plano precisa ter os 7 dias da semana, de 0 (segunda) a 6 (domingo)")
        self.dias.sort(key=lambda d: d.dia)
        return self
