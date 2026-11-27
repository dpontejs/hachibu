"""Registro da musculação: a sessão do dia, série a série, no estilo do Hevy.

Cada série é gravada quando o aluno a marca como feita: se o iPhone fechar o app no meio do treino, a sessão
continua de onde parou. A "última vez" de um exercício prefere o mesmo local (máquinas mudam de academia para
academia) e nunca conta a sessão em andamento.
"""

import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from hachibu.auth import UserId
from hachibu.db import Db
from hachibu.diario import hoje
from hachibu.treino.exercicios import por_id
from hachibu.treino.repositorio import plano_ativo

router = APIRouter(prefix="/api")
Local = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class SessaoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plano_dia: int | None = Field(default=None, ge=0, le=6)
    local: Local | None = None


class SerieIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordem_exercicio: int = Field(ge=0, le=40)
    ordem: int = Field(ge=0, le=30)
    carga_kg: float | None = Field(default=None, ge=0, le=1000)  # vazio = peso do corpo
    reps: int = Field(ge=1, le=100)


class LocalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local: Local | None = None


class ExercicioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercicio_id: str = Field(max_length=60)
    series: int = Field(default=3, ge=1, le=10)
    reps_min: int = Field(default=8, ge=1, le=30)
    reps_max: int = Field(default=12, ge=1, le=30)
    descanso_s: int = Field(default=90, ge=15, le=600)

    @model_validator(mode="after")
    def _faixa(self):
        if self.reps_max < self.reps_min:
            raise ValueError("reps_max menor que reps_min")
        return self


class TrocaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercicio_id: str = Field(max_length=60)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _exercicio_valido(exercicio_id: str) -> None:
    if por_id(exercicio_id) is None:
        raise HTTPException(422, "exercicio_inexistente")


def _sessao(db, user_id: int, id_: int, escrita: bool = False):
    row = db.execute("SELECT * FROM sessoes WHERE id = ? AND user_id = ?", (id_, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, "sessao_inexistente")
    if escrita and row["finalizada_em"] is not None:
        raise HTTPException(409, "sessao_finalizada")
    return row


def ultima_vez(
    db, user_id: int, exercicio_id: str, local: str | None, exceto: int | None = None
) -> dict | None:
    """Séries da última sessão com este exercício: do mesmo local, se houver; senão, de qualquer local."""

    def buscar(mesmo_local: bool):
        filtro = " AND lower(trim(s.local)) = lower(trim(?))" if mesmo_local else ""
        args: list = [user_id, exercicio_id, exceto or -1]
        if mesmo_local:
            args.append(local)
        return db.execute(
            "SELECT s.id, s.data, s.local FROM series x JOIN sessoes s ON s.id = x.sessao_id "
            "WHERE s.user_id = ? AND x.exercicio_id = ? AND s.id != ? AND s.finalizada_em IS NOT NULL"
            f"{filtro} "
            "ORDER BY s.iniciada_em DESC LIMIT 1",
            args,
        ).fetchone()

    sessao = (buscar(True) if local else None) or buscar(False)
    if sessao is None:
        return None
    series = db.execute(
        "SELECT carga_kg, reps FROM series WHERE sessao_id = ? AND exercicio_id = ? "
        "ORDER BY ordem_exercicio, ordem",
        (sessao["id"], exercicio_id),
    ).fetchall()
    return {"data": sessao["data"], "local": sessao["local"], "series": [dict(r) for r in series]}


def montar(db, user_id: int, sessao) -> dict:
    exercicios = []
    for e in db.execute(
        "SELECT * FROM sessao_exercicios WHERE sessao_id = ? ORDER BY ordem", (sessao["id"],)
    ):
        feitas = db.execute(
            "SELECT ordem, carga_kg, reps FROM series WHERE sessao_id = ? AND ordem_exercicio = ? "
            "ORDER BY ordem",
            (sessao["id"], e["ordem"]),
        ).fetchall()
        ex = por_id(e["exercicio_id"])
        exercicios.append(
            {
                "ordem": e["ordem"],
                "exercicio_id": e["exercicio_id"],
                "nome": ex.nome if ex else e["exercicio_id"],
                "series_planejadas": e["series_planejadas"],
                "reps_min": e["reps_min"],
                "reps_max": e["reps_max"],
                "descanso_s": e["descanso_s"],
                "feitas": [dict(f) for f in feitas],
                "ultima": ultima_vez(db, user_id, e["exercicio_id"], sessao["local"], exceto=sessao["id"]),
            }
        )
    return {
        "id": sessao["id"],
        "data": sessao["data"],
        "nome": sessao["nome"],
        "plano_dia": sessao["plano_dia"],
        "local": sessao["local"],
        "iniciada_em": sessao["iniciada_em"],
        "finalizada_em": sessao["finalizada_em"],
        "exercicios": exercicios,
    }


def _inserir_exercicio(db, sessao_id: int, ordem: int, e: ExercicioIn) -> None:
    db.execute(
        "INSERT INTO sessao_exercicios (sessao_id, ordem, exercicio_id, series_planejadas, reps_min, "
        "reps_max, descanso_s) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sessao_id, ordem, e.exercicio_id, e.series, e.reps_min, e.reps_max, e.descanso_s),
    )


@router.post("/sessoes", status_code=201)
def iniciar(dados: SessaoIn, request: Request, user_id: UserId, db: Db) -> dict:
    """Começa a sessão do dia do plano (copia os exercícios) ou um treino livre (vazio)."""
    exercicios, nome, plano_id = [], "Treino livre", None
    if dados.plano_dia is not None:
        ativo = plano_ativo(db, user_id)
        if ativo is None:
            raise HTTPException(404, "plano_inexistente")
        meta, plano = ativo
        dia = plano.dias[dados.plano_dia]
        if not dia.exercicios:
            raise HTTPException(422, "dia_sem_musculacao")
        exercicios, nome, plano_id = dia.exercicios, dia.nome, meta["id"]
    data = hoje(request.app.state.settings.app_tz).isoformat()
    db.execute("BEGIN IMMEDIATE")
    try:
        # Dentro da transação: dois "iniciar" ao mesmo tempo (rede instável na academia) não abrem duas.
        if db.execute(
            "SELECT 1 FROM sessoes WHERE user_id = ? AND tipo = 'musculacao' AND finalizada_em IS NULL",
            (user_id,),
        ).fetchone():
            raise HTTPException(409, "sessao_aberta")
        cur = db.execute(
            "INSERT INTO sessoes (user_id, tipo, data, nome, plano_id, plano_dia, local, iniciada_em) "
            "VALUES (?, 'musculacao', ?, ?, ?, ?, ?, ?)",
            (user_id, data, nome, plano_id, dados.plano_dia, dados.local, _agora()),
        )
        for ordem, e in enumerate(exercicios):
            _inserir_exercicio(
                db,
                cur.lastrowid,
                ordem,
                ExercicioIn(
                    exercicio_id=e.exercicio_id,
                    series=e.series,
                    reps_min=e.reps_min,
                    reps_max=e.reps_max,
                    descanso_s=e.descanso_s,
                ),
            )
        db.execute("COMMIT")
    except sqlite3.IntegrityError:
        db.execute("ROLLBACK")
        raise HTTPException(409, "sessao_aberta") from None
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return montar(db, user_id, _sessao(db, user_id, cur.lastrowid))


@router.get("/sessoes/aberta")
def aberta(user_id: UserId, db: Db) -> dict:
    row = db.execute(
        "SELECT * FROM sessoes WHERE user_id = ? AND tipo = 'musculacao' AND finalizada_em IS NULL",
        (user_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "sem_sessao_aberta")
    return montar(db, user_id, row)


@router.get("/sessoes")
def historico(user_id: UserId, db: Db, de: str, ate: str) -> list[dict]:
    """Sessões finalizadas no período, com o total de séries (para marcar os dias feitos)."""
    rows = db.execute(
        "SELECT s.id, s.data, s.nome, s.plano_dia, s.local, COUNT(x.ordem) AS series FROM sessoes s "
        "LEFT JOIN series x ON x.sessao_id = s.id WHERE s.user_id = ? AND s.finalizada_em IS NOT NULL "
        "AND s.data BETWEEN ? AND ? GROUP BY s.id ORDER BY s.data, s.id",
        (user_id, de, ate),
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/sessoes/{id_}")
def obter(id_: int, user_id: UserId, db: Db) -> dict:
    return montar(db, user_id, _sessao(db, user_id, id_))


@router.put("/sessoes/{id_}/series")
def marcar_serie(id_: int, dados: SerieIn, user_id: UserId, db: Db) -> dict:
    sessao = _sessao(db, user_id, id_, escrita=True)
    ex = db.execute(
        "SELECT exercicio_id FROM sessao_exercicios WHERE sessao_id = ? AND ordem = ?",
        (id_, dados.ordem_exercicio),
    ).fetchone()
    if ex is None:
        raise HTTPException(404, "exercicio_inexistente_na_sessao")
    db.execute(
        "INSERT INTO series (sessao_id, ordem_exercicio, ordem, exercicio_id, carga_kg, reps, feita_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(sessao_id, ordem_exercicio, ordem) DO UPDATE SET "
        "carga_kg = excluded.carga_kg, reps = excluded.reps, feita_em = excluded.feita_em",
        (id_, dados.ordem_exercicio, dados.ordem, ex["exercicio_id"], dados.carga_kg, dados.reps, _agora()),
    )
    return montar(db, user_id, sessao)


@router.delete("/sessoes/{id_}/series/{ordem_exercicio}/{ordem}")
def desmarcar_serie(id_: int, ordem_exercicio: int, ordem: int, user_id: UserId, db: Db) -> dict:
    sessao = _sessao(db, user_id, id_, escrita=True)
    db.execute(
        "DELETE FROM series WHERE sessao_id = ? AND ordem_exercicio = ? AND ordem = ?",
        (id_, ordem_exercicio, ordem),
    )
    return montar(db, user_id, sessao)


@router.patch("/sessoes/{id_}")
def mudar_local(id_: int, dados: LocalIn, user_id: UserId, db: Db) -> dict:
    _sessao(db, user_id, id_, escrita=True)
    db.execute("UPDATE sessoes SET local = ? WHERE id = ?", (dados.local, id_))
    return montar(db, user_id, _sessao(db, user_id, id_))


@router.post("/sessoes/{id_}/exercicios")
def acrescentar_exercicio(id_: int, dados: ExercicioIn, user_id: UserId, db: Db) -> dict:
    sessao = _sessao(db, user_id, id_, escrita=True)
    _exercicio_valido(dados.exercicio_id)
    db.execute("BEGIN IMMEDIATE")
    try:
        proxima = db.execute(
            "SELECT COALESCE(MAX(ordem) + 1, 0) AS n FROM sessao_exercicios WHERE sessao_id = ?", (id_,)
        ).fetchone()["n"]
        if proxima > 40:
            raise HTTPException(422, "exercicios_demais")
        _inserir_exercicio(db, id_, proxima, dados)
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return montar(db, user_id, sessao)


@router.put("/sessoes/{id_}/exercicios/{ordem}")
def trocar_exercicio(id_: int, ordem: int, dados: TrocaIn, user_id: UserId, db: Db) -> dict:
    """Troca só neste dia: o plano não muda (para mudar o plano, é com o coach)."""
    sessao = _sessao(db, user_id, id_, escrita=True)
    _exercicio_valido(dados.exercicio_id)
    atual = db.execute(
        "SELECT exercicio_id FROM sessao_exercicios WHERE sessao_id = ? AND ordem = ?", (id_, ordem)
    ).fetchone()
    if atual is not None and atual["exercicio_id"] == dados.exercicio_id:
        return montar(db, user_id, sessao)  # o mesmo exercício: nada muda, nenhuma série se perde
    cur = db.execute(
        "UPDATE sessao_exercicios SET exercicio_id = ? WHERE sessao_id = ? AND ordem = ?",
        (dados.exercicio_id, id_, ordem),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "exercicio_inexistente_na_sessao")
    # Séries já feitas no exercício antigo saem: elas eram de outro movimento.
    db.execute("DELETE FROM series WHERE sessao_id = ? AND ordem_exercicio = ?", (id_, ordem))
    return montar(db, user_id, sessao)


@router.post("/sessoes/{id_}/finalizar")
def finalizar(id_: int, user_id: UserId, db: Db) -> dict:
    sessao = _sessao(db, user_id, id_, escrita=True)
    fim = datetime.now(UTC)
    db.execute("UPDATE sessoes SET finalizada_em = ? WHERE id = ?", (fim.isoformat(), id_))
    totais = db.execute(
        "SELECT COUNT(*) AS series, COALESCE(SUM(COALESCE(carga_kg, 0) * reps), 0) AS volume FROM series "
        "WHERE sessao_id = ?",
        (id_,),
    ).fetchone()
    duracao = (fim - datetime.fromisoformat(sessao["iniciada_em"])).total_seconds() / 60
    return {
        "duracao_min": round(duracao),
        "series": totais["series"],
        "volume_kg": round(totais["volume"], 1),
    }


@router.delete("/sessoes/{id_}", status_code=204)
def descartar(id_: int, user_id: UserId, db: Db) -> Response:
    _sessao(db, user_id, id_, escrita=True)
    db.execute("DELETE FROM sessoes WHERE id = ?", (id_,))
    return Response(status_code=204)


@router.get("/exercicios/{exercicio_id}/ultima")
def ultima(exercicio_id: str, user_id: UserId, db: Db, local: str | None = None) -> dict | None:
    return ultima_vez(db, user_id, exercicio_id, local)


@router.get("/locais")
def locais(user_id: UserId, db: Db) -> list[str]:
    """Locais já usados, os mais recentes primeiro (sugestões no campo de local)."""
    rows = db.execute(
        "SELECT local, MAX(iniciada_em) AS ultimo FROM sessoes WHERE user_id = ? AND local IS NOT NULL "
        "GROUP BY local ORDER BY ultimo DESC",
        (user_id,),
    ).fetchall()
    return [r["local"] for r in rows]
