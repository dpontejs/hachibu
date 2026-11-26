from fastapi.testclient import TestClient

from tests.conftest import CONVITE

SENHA = "senha-forte-1"


def signup(client, email="a@x.com", senha=SENHA, convite=CONVITE):
    return client.post("/api/auth/signup", json={"email": email, "senha": senha, "convite": convite})


def test_signup_com_convite_valido(client):
    r = signup(client)
    assert r.status_code == 201
    assert "hachibu_session" in r.cookies
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"email": "a@x.com", "perfil_completo": False}


def test_signup_convite_errado(client):
    assert signup(client, convite="errado").status_code == 403
    assert client.get("/api/me").status_code == 401


def test_signup_email_repetido(client):
    signup(client)
    assert signup(TestClient(client.app)).status_code == 409


def test_email_normalizado(client):
    signup(client, email="  Diego@X.com ")
    assert client.get("/api/me").json()["email"] == "diego@x.com"
    outro = TestClient(client.app)
    assert signup(outro, email="diego@x.com").status_code == 409
    assert outro.post("/api/auth/login", json={"email": "DIEGO@x.com", "senha": SENHA}).status_code == 200


def test_email_invalido(client):
    assert signup(client, email="sem-arroba").status_code == 422


def test_senha_curta(client):
    assert signup(client, senha="1234567").status_code == 422


def test_login_ok(client):
    signup(client)
    novo = TestClient(client.app)
    r = novo.post("/api/auth/login", json={"email": "a@x.com", "senha": SENHA})
    assert r.status_code == 200
    assert novo.get("/api/me").status_code == 200


def test_login_senha_errada(client):
    signup(client)
    novo = TestClient(client.app)
    assert novo.post("/api/auth/login", json={"email": "a@x.com", "senha": "errada-123"}).status_code == 401
    assert novo.post("/api/auth/login", json={"email": "ninguem@x.com", "senha": SENHA}).status_code == 401


def test_login_rate_limit(client):
    signup(client)
    novo = TestClient(client.app)
    for _ in range(5):
        assert (
            novo.post("/api/auth/login", json={"email": "a@x.com", "senha": "errada-123"}).status_code == 401
        )
    # Bloqueado mesmo com a senha certa até a janela passar.
    assert novo.post("/api/auth/login", json={"email": "a@x.com", "senha": SENHA}).status_code == 429


def test_convite_errado_conta_no_rate_limit(client):
    for _ in range(5):
        assert signup(client, convite="chute").status_code == 403
    assert signup(client).status_code == 429


def test_cookie_invalido(client):
    client.cookies.set("hachibu_session", "lixo.assinatura.errada")
    assert client.get("/api/me").status_code == 401


def test_logout_encerra_sessao(client):
    signup(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_me_sem_login(client):
    assert client.get("/api/me").status_code == 401


def test_falhas_de_outros_ips_nao_trancam_o_login(client):
    signup(client)
    from datetime import UTC, datetime

    for i in range(30):
        client.app.state.login_limiter.falhou(f"10.0.0.{i}", datetime.now(UTC))
    novo = TestClient(client.app)
    assert novo.post("/api/auth/login", json={"email": "a@x.com", "senha": SENHA}).status_code == 200
