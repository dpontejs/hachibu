"""Rotas do treino: a semana com os exercícios e a corrida da semana atual, e o catálogo.

Não há rota que gere o plano: ele nasce da conversa com o coach (rascunho em código + proposta aprovada).
"""

from fastapi import APIRouter, HTTPException

from hachibu.auth import UserId
from hachibu.db import Db
from hachibu.memorias import listar as listar_memorias
from hachibu.perfil import ler_perfil
from hachibu.treino.exercicios import buscar, por_id
from hachibu.treino.modelos import PlanoIn
from hachibu.treino.repositorio import plano_ativo, semana_corrida
from hachibu.treino.validador import corrida_efetiva, validar_plano

router = APIRouter(prefix="/api")


def _perfil(db, user_id: int):
    perfil = ler_perfil(db, user_id)
    if perfil is None:
        raise HTTPException(409, "perfil_incompleto")
    return perfil


def montar_semana(plano: PlanoIn, semana: int) -> list[dict]:
    """Dias com o nome de cada exercício e a corrida já resolvida para a semana atual da progressão."""
    dias = []
    for dia in plano.dias:
        exercicios = []
        for e in dia.exercicios:
            ex = por_id(e.exercicio_id)
            exercicios.append(
                e.model_dump()
                | {"nome": ex.nome if ex else e.exercicio_id, "grupo": ex.grupo if ex else None}
            )
        corrida = corrida_efetiva(dia.corrida, semana)
        dias.append(
            {
                "dia": dia.dia,
                "nome": dia.nome,
                "exercicios": exercicios,
                "corrida": corrida.model_dump() if corrida else None,
            }
        )
    return dias


@router.get("/plano")
def obter_plano(user_id: UserId, db: Db) -> dict:
    ativo = plano_ativo(db, user_id)
    if ativo is None:
        raise HTTPException(404, "plano_inexistente")
    meta, plano = ativo
    perfil = _perfil(db, user_id)
    semana = semana_corrida(db, user_id)
    condicoes = any(m.tipo == "condicao" for m in listar_memorias(db, user_id))
    return {
        "versao": meta["versao"],
        "origem": meta["origem"],
        "criado_em": meta["criado_em"],
        "semana_corrida": semana,
        "dias": montar_semana(plano, semana),
        # O perfil pode ter mudado depois do plano: o aluno vê o que deixou de valer.
        "avisos": validar_plano(plano, perfil, semana_corrida=semana),
        "tem_condicoes": condicoes or bool(perfil.condicoes_saude and perfil.condicoes_saude.strip()),
    }


@router.get("/exercicios")
def buscar_exercicios(user_id: UserId, q: str = "") -> list[dict]:
    return [
        {"id": e.id, "nome": e.nome, "grupo": e.grupo, "equipamentos": list(e.equipamentos)}
        for e in buscar(q)
    ]
