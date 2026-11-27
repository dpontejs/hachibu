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
    tipo: Literal["corrida_caminhada", "leve", "intervalado", "longao"]
    duracao_min: int = Field(ge=5, le=240)
    corre_min: float | None = Field(default=None, ge=0, le=240)
    anda_min: float | None = Field(default=None, ge=0, le=30)
    repeticoes: int | None = Field(default=None, ge=1, le=30)
    esforco_alvo: str = Field(max_length=10)

    @model_validator(mode="after")
    def _coerente(self):
        if self.progressao and self.tipo != "corrida_caminhada":
            raise ValueError("progressao só vale para tipo corrida_caminhada")
        # O conversor de schema do Gemini obriga todos os campos: blocos fora de corrida e caminhada
        # (ou zerados) são enchimento e viram None, para não virar diferença falsa nem plano estranho.
        if self.tipo != "corrida_caminhada" or not self.corre_min:
            self.corre_min = self.anda_min = self.repeticoes = None
        return self


class CardioPlano(BaseModel):
    """Cardio que não é corrida (bicicleta, elíptico, caminhada…). Leve não conta como treino pesado."""

    model_config = ConfigDict(extra="forbid")
    modalidade: Literal["bicicleta", "eliptico", "caminhada", "escada", "remo"]
    duracao_min: int = Field(ge=5, le=120)
    intensidade: Literal["leve", "moderada"]


class DiaPlano(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _recuperacao_antiga(cls, dados):
        """Planos gravados antes do cardio guardavam a recuperação como tipo de corrida: vira cardio leve.

        As versões são fotos imutáveis no banco, então o formato antigo precisa continuar legível.
        """
        if isinstance(dados, dict):
            corrida = dados.get("corrida")
            if isinstance(corrida, dict) and corrida.get("tipo") == "recuperacao":
                dados = {
                    **dados,
                    "corrida": None,
                    "cardio": dados.get("cardio")
                    or {
                        "modalidade": "caminhada",
                        "duracao_min": corrida.get("duracao_min", 30),
                        "intensidade": "leve",
                    },
                }
        return dados

    dia: int = Field(ge=0, le=6)  # 0 = segunda
    nome: str = Field(max_length=40)
    exercicios: list[ExercicioPlano] = Field(default_factory=list, max_length=15)
    corrida: CorridaPlano | None = None
    cardio: CardioPlano | None = None


class PlanoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dias: list[DiaPlano] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def _sete_dias(self):
        if sorted(d.dia for d in self.dias) != list(range(7)):
            raise ValueError("o plano precisa ter os 7 dias da semana, de 0 (segunda) a 6 (domingo)")
        self.dias.sort(key=lambda d: d.dia)
        return self
