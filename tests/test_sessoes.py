"""Registro da musculação: sessão do dia, séries salvas uma a uma, última carga e isolamento."""

import pytest

from hachibu.db import connect
from hachibu.metas import PerfilIn
from hachibu.treino.base import gerar_plano_base
from hachibu.treino.repositorio import gravar_plano
from tests.test_metas import BASE


@pytest.fixture
def com_plano(settings, aluno):
    plano, _ = gerar_plano_base(PerfilIn(**BASE))
    db = connect(settings.db_path)
    gravar_plano(db, 1, plano, "coach")
    db.close()
    return aluno


def iniciar(c, **corpo):
    r = c.post("/api/sessoes", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def serie(c, sessao, ordem_exercicio, ordem, carga, reps):
    r = c.put(
        f"/api/sessoes/{sessao}/series",
        json={"ordem_exercicio": ordem_exercicio, "ordem": ordem, "carga_kg": carga, "reps": reps},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_iniciar_o_treino_do_dia_copia_os_exercicios_do_plano(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    assert s["nome"] == "Superior A" and s["finalizada_em"] is None
    primeiro = s["exercicios"][0]
    assert primeiro["exercicio_id"] == "supino_reto" and primeiro["nome"].startswith("Supino")
    assert primeiro["series_planejadas"] == 3 and primeiro["feitas"] == [] and primeiro["ultima"] is None


def test_treino_livre_comeca_vazio_e_aceita_exercicio(com_plano):
    s = iniciar(com_plano)
    assert s["nome"] == "Treino livre" and s["exercicios"] == []
    r = com_plano.post(f"/api/sessoes/{s['id']}/exercicios", json={"exercicio_id": "rosca_direta"})
    assert r.status_code == 200 and r.json()["exercicios"][0]["exercicio_id"] == "rosca_direta"


def test_uma_sessao_aberta_por_vez_e_ela_pode_ser_retomada(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    r = com_plano.post("/api/sessoes", json={"plano_dia": 1})
    assert (r.status_code, r.json()["detail"]) == (409, "sessao_aberta")
    serie(com_plano, s["id"], 0, 0, 40, 10)
    aberta = com_plano.get("/api/sessoes/aberta").json()
    assert aberta["id"] == s["id"]
    assert aberta["exercicios"][0]["feitas"] == [{"ordem": 0, "carga_kg": 40, "reps": 10}]


def test_serie_marcada_de_novo_atualiza_e_desmarcar_apaga(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    serie(com_plano, s["id"], 0, 0, 40, 10)
    depois = serie(com_plano, s["id"], 0, 0, 42.5, 8)
    assert depois["exercicios"][0]["feitas"] == [{"ordem": 0, "carga_kg": 42.5, "reps": 8}]
    assert com_plano.delete(f"/api/sessoes/{s['id']}/series/0/0").status_code == 200
    assert com_plano.get(f"/api/sessoes/{s['id']}").json()["exercicios"][0]["feitas"] == []


def test_peso_corporal_aceita_carga_vazia_e_numeros_absurdos_sao_recusados(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    assert serie(com_plano, s["id"], 0, 0, None, 12)["exercicios"][0]["feitas"][0]["carga_kg"] is None
    for carga, reps in ((2000, 10), (40, 0), (40, 200), (-5, 10)):
        r = com_plano.put(
            f"/api/sessoes/{s['id']}/series",
            json={"ordem_exercicio": 0, "ordem": 1, "carga_kg": carga, "reps": reps},
        )
        assert r.status_code == 422, (carga, reps)


def test_serie_de_exercicio_que_nao_existe_na_sessao_404(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    r = com_plano.put(f"/api/sessoes/{s['id']}/series", json={"ordem_exercicio": 40, "ordem": 0, "reps": 10})
    assert r.status_code == 404


def test_finalizar_devolve_resumo_e_trava_a_sessao(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    serie(com_plano, s["id"], 0, 0, 40, 10)
    serie(com_plano, s["id"], 0, 1, 40, 8)
    r = com_plano.post(f"/api/sessoes/{s['id']}/finalizar")
    assert r.status_code == 200
    resumo = r.json()
    assert resumo["series"] == 2 and resumo["volume_kg"] == 720 and resumo["duracao_min"] >= 0
    assert com_plano.get("/api/sessoes/aberta").status_code == 404
    r = com_plano.put(f"/api/sessoes/{s['id']}/series", json={"ordem_exercicio": 0, "ordem": 2, "reps": 10})
    assert (r.status_code, r.json()["detail"]) == (409, "sessao_finalizada")


def test_ultima_carga_prefere_o_mesmo_local(com_plano):
    a = iniciar(com_plano, plano_dia=0, local="Smart Fit centro")
    serie(com_plano, a["id"], 0, 0, 30, 10)
    com_plano.post(f"/api/sessoes/{a['id']}/finalizar")
    b = iniciar(com_plano, plano_dia=0, local="Academia do prédio")
    serie(com_plano, b["id"], 0, 0, 24, 10)
    com_plano.post(f"/api/sessoes/{b['id']}/finalizar")

    ultima = com_plano.get("/api/exercicios/supino_reto/ultima", params={"local": "Smart Fit centro"}).json()
    assert ultima["local"] == "Smart Fit centro" and ultima["series"] == [{"carga_kg": 30, "reps": 10}]
    assert com_plano.get("/api/exercicios/supino_reto/ultima").json()["series"][0]["carga_kg"] == 24
    # Sem registro naquele local, vale a última de qualquer local.
    outro = com_plano.get("/api/exercicios/supino_reto/ultima", params={"local": "Hotel"}).json()
    assert outro["series"][0]["carga_kg"] == 24


def test_sessao_nova_ja_traz_a_ultima_vez_do_mesmo_local(com_plano):
    a = iniciar(com_plano, plano_dia=0, local="Smart Fit centro")
    serie(com_plano, a["id"], 0, 0, 30, 10)
    com_plano.post(f"/api/sessoes/{a['id']}/finalizar")
    b = iniciar(com_plano, plano_dia=0, local="Smart Fit centro")
    assert b["exercicios"][0]["ultima"]["series"] == [{"carga_kg": 30, "reps": 10}]
    # A sessão atual não conta como "última".
    serie(com_plano, b["id"], 0, 0, 35, 10)
    assert (
        com_plano.get(f"/api/sessoes/{b['id']}").json()["exercicios"][0]["ultima"]["series"][0]["carga_kg"]
        == 30
    )


def test_trocar_exercicio_so_no_dia_nao_muda_o_plano(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    r = com_plano.put(f"/api/sessoes/{s['id']}/exercicios/0", json={"exercicio_id": "supino_halteres"})
    assert r.status_code == 200 and r.json()["exercicios"][0]["exercicio_id"] == "supino_halteres"
    assert com_plano.get("/api/plano").json()["dias"][0]["exercicios"][0]["exercicio_id"] == "supino_reto"


def test_trocar_por_exercicio_inexistente_422(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    r = com_plano.put(f"/api/sessoes/{s['id']}/exercicios/0", json={"exercicio_id": "voo_do_dragao"})
    assert r.status_code == 422


def test_locais_usados_e_descartar_sessao(com_plano):
    s = iniciar(com_plano, plano_dia=0, local="Smart Fit centro")
    com_plano.patch(f"/api/sessoes/{s['id']}", json={"local": "Academia do prédio"})
    assert com_plano.get("/api/locais").json() == ["Academia do prédio"]
    assert com_plano.delete(f"/api/sessoes/{s['id']}").status_code == 204
    assert com_plano.get("/api/sessoes/aberta").status_code == 404


def test_historico_da_semana_marca_os_dias_feitos(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    serie(com_plano, s["id"], 0, 0, 40, 10)
    com_plano.post(f"/api/sessoes/{s['id']}/finalizar")
    lista = com_plano.get("/api/sessoes", params={"de": "2000-01-01", "ate": "2100-01-01"}).json()
    assert len(lista) == 1 and lista[0]["plano_dia"] == 0 and lista[0]["series"] == 1


def test_sessao_de_outro_usuario_404(com_plano, make_user):
    s = iniciar(com_plano, plano_dia=0)
    outro = make_user("b@x.com")
    outro.put("/api/perfil", json=BASE)
    assert outro.get(f"/api/sessoes/{s['id']}").status_code == 404
    r = outro.put(f"/api/sessoes/{s['id']}/series", json={"ordem_exercicio": 0, "ordem": 0, "reps": 10})
    assert r.status_code == 404
    assert outro.post(f"/api/sessoes/{s['id']}/finalizar").status_code == 404
    assert outro.get("/api/exercicios/supino_reto/ultima").json() is None


# ---------- achados da revisão ----------


def test_dois_iniciar_ao_mesmo_tempo_um_vira_409(com_plano):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(4) as pool:
        codigos = sorted(
            pool.map(lambda _: com_plano.post("/api/sessoes", json={"plano_dia": 0}).status_code, range(4))
        )
    assert codigos == [201, 409, 409, 409]


def test_ultima_vez_nao_conta_sessao_em_andamento(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    serie(com_plano, s["id"], 0, 0, 40, 10)
    assert com_plano.get("/api/exercicios/supino_reto/ultima").json() is None


def test_local_ignora_maiusculas_e_espacos(com_plano):
    a = iniciar(com_plano, plano_dia=0, local="Smart Fit")
    serie(com_plano, a["id"], 0, 0, 30, 10)
    com_plano.post(f"/api/sessoes/{a['id']}/finalizar")
    b = iniciar(com_plano, plano_dia=0, local="Outra")
    serie(com_plano, b["id"], 0, 0, 24, 10)
    com_plano.post(f"/api/sessoes/{b['id']}/finalizar")
    ultima = com_plano.get("/api/exercicios/supino_reto/ultima", params={"local": "  smart fit "}).json()
    assert ultima["series"][0]["carga_kg"] == 30


def test_trocar_pelo_mesmo_exercicio_nao_apaga_as_series(com_plano):
    s = iniciar(com_plano, plano_dia=0)
    serie(com_plano, s["id"], 0, 0, 40, 10)
    r = com_plano.put(f"/api/sessoes/{s['id']}/exercicios/0", json={"exercicio_id": "supino_reto"})
    assert r.json()["exercicios"][0]["feitas"] == [{"ordem": 0, "carga_kg": 40, "reps": 10}]


def test_exercicio_com_faixa_invertida_422(com_plano):
    s = iniciar(com_plano)
    r = com_plano.post(
        f"/api/sessoes/{s['id']}/exercicios",
        json={"exercicio_id": "rosca_direta", "reps_min": 12, "reps_max": 8},
    )
    assert r.status_code == 422


def test_dia_sem_musculacao_nao_vira_sessao(settings, aluno):
    from hachibu.treino.modelos import DiaPlano, PlanoIn

    plano = PlanoIn(dias=[DiaPlano(dia=i, nome="Descanso") for i in range(7)])
    db = connect(settings.db_path)
    gravar_plano(db, 1, plano, "coach")
    db.close()
    r = aluno.post("/api/sessoes", json={"plano_dia": 2})
    assert (r.status_code, r.json()["detail"]) == (422, "dia_sem_musculacao")
