"""Conversas anteriores do coach: só as do usuário, mais recentes primeiro, com título e pendência."""

import sqlite3
from datetime import UTC, datetime

from tests.coach_fake import chamada, roteiro
from tests.test_coach_rotas import enviar
from tests.test_metas import BASE


def conversas(c) -> list[dict]:
    r = c.get("/api/coach/conversas")
    assert r.status_code == 200, r.text
    return r.json()["conversas"]


def test_lista_conversas_mais_recentes_primeiro(app, aluno):
    app.state.modelo_coach = roteiro("Oi!", "Olá de novo!", "Certo.")
    primeira = enviar(aluno, "como está meu dia?").json()["thread_id"]
    segunda = enviar(aluno, "monta um treino").json()["thread_id"]
    lista = conversas(aluno)
    assert [c["thread_id"] for c in lista] == [segunda, primeira]
    assert lista[1]["titulo"] == "como está meu dia?"
    assert lista[0]["pendente"] is False

    enviar(aluno, "e agora?", thread_id=primeira)
    lista = conversas(aluno)
    assert [c["thread_id"] for c in lista] == [primeira, segunda]
    assert lista[0]["titulo"] == "como está meu dia?"  # o título é a primeira fala, não a última


def test_lista_nao_mostra_conversas_de_outro_usuario(app, aluno, make_user):
    app.state.modelo_coach = roteiro("Oi!")
    enviar(aluno, "segredo do aluno")
    intruso = make_user("b@x.com")
    intruso.put("/api/perfil", json=BASE)
    assert conversas(intruso) == []


def test_titulo_longo_e_cortado(app, aluno):
    app.state.modelo_coach = roteiro("Ok.")
    enviar(aluno, "almocei " + "arroz feijão " * 10)
    titulo = conversas(aluno)[0]["titulo"]
    assert len(titulo) <= 60 and titulo.endswith("…")


def test_conversa_com_aprovacao_pendente_aparece_marcada(app, aluno):
    app.state.modelo_coach = roteiro(chamada("ajustar_metas", {"kcal": 2400, "justificativa": "x"}), "ok")
    enviar(aluno, "baixa minha meta")
    assert conversas(aluno)[0]["pendente"] is True


def test_conversa_antiga_sem_titulo_ganha_o_da_primeira_fala(app, settings, aluno):
    app.state.modelo_coach = roteiro("Oi!")
    thread = enviar(aluno, "conversa de antes da lista").json()["thread_id"]
    # Simula uma conversa criada antes da migração: sem título gravado.
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("UPDATE coach_threads SET titulo = '' WHERE thread_id = ?", (thread,))
    assert conversas(aluno)[0]["titulo"] == "conversa de antes da lista"


def test_conversa_sem_nenhuma_mensagem_salva_nao_aparece(app, settings, aluno):
    # Registro criado mas o modelo falhou antes de salvar qualquer coisa: não há o que reabrir.
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO coach_threads (thread_id, user_id, criado_em, atualizado_em, titulo) "
            "VALUES ('vazia', 1, ?, ?, '')",
            (datetime.now(UTC).isoformat(),) * 2,
        )
    app.state.modelo_coach = roteiro("Oi!")
    assert conversas(aluno) == []
