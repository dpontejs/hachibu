"""Catálogo de exercícios: o plano e o histórico apontam para um id estável.

Sem o catálogo, o mesmo exercício apareceria com nomes diferentes ("supino reto", "supino com barra") e a
"última carga" se partiria em duas.
"""

import unicodedata
from dataclasses import dataclass

ACADEMIA = ("academia",)
HALTERES = ("academia", "casa_halteres")
CORPO = ("academia", "casa_halteres", "peso_corporal")
PERNAS = {"quadriceps", "posterior", "gluteos", "panturrilha"}


@dataclass(frozen=True)
class Exercicio:
    id: str
    nome: str
    grupo: str
    padrao: str
    equipamentos: tuple[str, ...]


def _e(id_: str, nome: str, grupo: str, padrao: str, equipamentos: tuple[str, ...]) -> Exercicio:
    return Exercicio(id_, nome, grupo, padrao, equipamentos)


CATALOGO: list[Exercicio] = [
    # peito
    _e("supino_reto", "Supino reto com barra", "peito", "empurrar_horizontal", ACADEMIA),
    _e("supino_inclinado", "Supino inclinado com barra", "peito", "empurrar_horizontal", ACADEMIA),
    _e("supino_halteres", "Supino reto com halteres", "peito", "empurrar_horizontal", HALTERES),
    _e(
        "supino_inclinado_halteres", "Supino inclinado com halteres", "peito", "empurrar_horizontal", HALTERES
    ),
    _e("crucifixo_halteres", "Crucifixo com halteres", "peito", "isolado", HALTERES),
    _e("crossover", "Crossover na polia", "peito", "isolado", ACADEMIA),
    _e("supino_maquina", "Supino na máquina", "peito", "empurrar_horizontal", ACADEMIA),
    _e("flexao", "Flexão de braços", "peito", "empurrar_horizontal", CORPO),
    _e("flexao_declinada", "Flexão com pés elevados", "peito", "empurrar_horizontal", CORPO),
    # costas
    _e("puxada_frente", "Puxada na frente (polia)", "costas", "puxar_vertical", ACADEMIA),
    _e("remada_baixa", "Remada baixa na polia", "costas", "puxar_horizontal", ACADEMIA),
    _e("remada_curvada", "Remada curvada com barra", "costas", "puxar_horizontal", ACADEMIA),
    _e("remada_unilateral", "Remada unilateral com halter", "costas", "puxar_horizontal", HALTERES),
    _e("pullover_halter", "Pullover com halter", "costas", "puxar_vertical", HALTERES),
    _e("barra_fixa", "Barra fixa", "costas", "puxar_vertical", CORPO),
    _e("remada_invertida", "Remada invertida", "costas", "puxar_horizontal", CORPO),
    _e("superman", "Superman", "costas", "core", CORPO),
    # ombros
    _e("desenvolvimento_barra", "Desenvolvimento com barra", "ombros", "empurrar_vertical", ACADEMIA),
    _e("desenvolvimento_halteres", "Desenvolvimento com halteres", "ombros", "empurrar_vertical", HALTERES),
    _e("elevacao_lateral", "Elevação lateral com halteres", "ombros", "isolado", HALTERES),
    _e("crucifixo_inverso", "Crucifixo inverso com halteres", "ombros", "isolado", HALTERES),
    _e("face_pull", "Face pull na polia", "ombros", "isolado", ACADEMIA),
    _e("flexao_pike", "Flexão pike", "ombros", "empurrar_vertical", CORPO),
    # braços
    _e("rosca_direta", "Rosca direta com barra", "biceps", "isolado", ACADEMIA),
    _e("rosca_halteres", "Rosca alternada com halteres", "biceps", "isolado", HALTERES),
    _e("rosca_martelo", "Rosca martelo", "biceps", "isolado", HALTERES),
    _e("triceps_corda", "Tríceps na polia com corda", "triceps", "isolado", ACADEMIA),
    _e("triceps_testa", "Tríceps testa com halteres", "triceps", "isolado", HALTERES),
    _e("triceps_frances", "Tríceps francês com halter", "triceps", "isolado", HALTERES),
    _e("mergulho_banco", "Mergulho no banco", "triceps", "empurrar_vertical", CORPO),
    _e("flexao_diamante", "Flexão diamante", "triceps", "empurrar_horizontal", CORPO),
    # quadríceps
    _e("agachamento_livre", "Agachamento livre com barra", "quadriceps", "agachar", ACADEMIA),
    _e("agachamento_goblet", "Agachamento goblet", "quadriceps", "agachar", HALTERES),
    _e("agachamento_corporal", "Agachamento livre (peso do corpo)", "quadriceps", "agachar", CORPO),
    _e("leg_press", "Leg press", "quadriceps", "agachar", ACADEMIA),
    _e("cadeira_extensora", "Cadeira extensora", "quadriceps", "isolado", ACADEMIA),
    _e("afundo_halteres", "Afundo com halteres", "quadriceps", "afundo", HALTERES),
    _e("afundo", "Afundo (peso do corpo)", "quadriceps", "afundo", CORPO),
    _e("bulgaro_halteres", "Agachamento búlgaro com halteres", "quadriceps", "afundo", HALTERES),
    _e("bulgaro", "Agachamento búlgaro (peso do corpo)", "quadriceps", "afundo", CORPO),
    # posterior
    _e("stiff_barra", "Stiff com barra", "posterior", "dobrar_quadril", ACADEMIA),
    _e("stiff_halteres", "Stiff com halteres", "posterior", "dobrar_quadril", HALTERES),
    _e("levantamento_terra", "Levantamento terra", "posterior", "dobrar_quadril", ACADEMIA),
    _e("mesa_flexora", "Mesa flexora", "posterior", "isolado", ACADEMIA),
    _e("stiff_unilateral", "Stiff unilateral (peso do corpo)", "posterior", "dobrar_quadril", CORPO),
    _e("flexao_nordica", "Flexão nórdica", "posterior", "isolado", CORPO),
    # glúteos
    _e("elevacao_quadril_barra", "Elevação de quadril com barra", "gluteos", "dobrar_quadril", ACADEMIA),
    _e("elevacao_quadril_halter", "Elevação de quadril com halter", "gluteos", "dobrar_quadril", HALTERES),
    _e("ponte_gluteo", "Ponte de glúteo", "gluteos", "dobrar_quadril", CORPO),
    _e("abducao_maquina", "Cadeira abdutora", "gluteos", "isolado", ACADEMIA),
    # panturrilha
    _e("panturrilha_em_pe", "Panturrilha em pé na máquina", "panturrilha", "panturrilha", ACADEMIA),
    _e("panturrilha_sentado", "Panturrilha sentado", "panturrilha", "panturrilha", ACADEMIA),
    _e("panturrilha_halter", "Panturrilha em pé com halter", "panturrilha", "panturrilha", HALTERES),
    _e("panturrilha_degrau", "Panturrilha no degrau", "panturrilha", "panturrilha", CORPO),
    # core
    _e("prancha", "Prancha", "core", "core", CORPO),
    _e("prancha_lateral", "Prancha lateral", "core", "core", CORPO),
    _e("abdominal_infra", "Abdominal infra", "core", "core", CORPO),
    _e("abdominal_polia", "Abdominal na polia", "core", "core", ACADEMIA),
    _e("dead_bug", "Dead bug", "core", "core", CORPO),
]

_POR_ID = {e.id: e for e in CATALOGO}


def por_id(id_: str) -> Exercicio | None:
    return _POR_ID.get(id_)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).casefold()


def buscar(q: str) -> list[Exercicio]:
    termo = _sem_acento(q.strip())
    return [e for e in CATALOGO if termo in _sem_acento(e.nome) or termo in e.id]
