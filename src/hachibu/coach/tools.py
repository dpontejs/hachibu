"""Tools do agente: as funções puras de `ferramentas` com db, usuário e relógio fechados na requisição.

O schema que o modelo vê só tem os argumentos da tarefa. O usuário vem da sessão, nunca do modelo.
"""

import json
from collections.abc import Callable
from datetime import datetime

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from hachibu.coach import ferramentas as f
from hachibu.coach.skills import criar_tool_carregar_skill
from hachibu.db import connect


class ItemRefeicao(BaseModel):
    alimento_id: int = Field(description="id do alimento na TACO (use buscar_alimento_taco)")
    gramas: float = Field(description="porção em gramas")


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, default=str)


def criar_tools(db_path: str, user_id: int, agora: Callable[[], datetime]) -> list[BaseTool]:
    def rodar(funcao, *args, **kwargs) -> str:
        db = connect(db_path)
        try:
            return _json(funcao(db, user_id, *args, **kwargs))
        except f.ErroFerramenta as e:
            return f"erro: {e}"
        finally:
            db.close()

    @tool
    def ler_perfil() -> str:
        """Perfil do aluno: sexo, idade, altura, peso, objetivo, nível, dias e minutos de treino, equipamento,
        % de gordura, cintura, condições de saúde e meta do nutricionista, se houver."""
        return rodar(f.ler_perfil)

    @tool
    def ler_diagnostico() -> str:
        """Taxa basal, gasto diário, relação cintura/altura (alerta a partir de 0,5) e metas com a origem."""
        return rodar(f.ler_diagnostico)

    @tool
    def saldo_do_dia() -> str:
        """Metas, quanto o aluno já consumiu hoje, quanto falta, água e as refeições do dia."""
        return rodar(f.saldo_do_dia, agora())

    @tool
    def buscar_alimento_taco(termo: str) -> str:
        """Busca alimentos na TACO pelo nome (ex.: "frango grelhado"). Devolve id e valores por 100 g."""
        return rodar(f.buscar_alimento_taco, termo)

    @tool
    def registrar_refeicao(nome: str, itens: list[ItemRefeicao]) -> str:
        """Registra uma refeição no diário de hoje. Cada item é um alimento da TACO (alimento_id) com gramas.
        As calorias e macros são calculados pelo sistema. Use só depois que o aluno confirmar os itens."""
        return rodar(f.registrar_refeicao, nome, [i.model_dump() for i in itens], agora())

    @tool
    def registrar_agua(ml: int) -> str:
        """Registra água bebida agora, em ml (1 a 2000)."""
        return rodar(f.registrar_agua, ml, agora())

    @tool
    def ajustar_metas(
        kcal: int,
        justificativa: str,
        proteina_g: int | None = None,
        carbo_g: int | None = None,
        gordura_g: int | None = None,
    ) -> str:
        """Propõe uma nova meta diária. O aluno vê a proposta e a justificativa e aprova antes de valer.
        Macros omitidos são completados pela fórmula. Metas abaixo do piso ou com déficit acima de 25% do
        gasto diário são recusadas pelo sistema."""
        return rodar(f.aplicar_ajuste_metas, kcal, agora(), proteina_g, carbo_g, gordura_g)

    return [
        ler_perfil,
        ler_diagnostico,
        saldo_do_dia,
        buscar_alimento_taco,
        registrar_refeicao,
        registrar_agua,
        ajustar_metas,
        criar_tool_carregar_skill(),
    ]
