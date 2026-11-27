import pytest
from fastapi.testclient import TestClient

from hachibu.app import create_app
from hachibu.config import Settings

MIGRACOES = [
    "001_inicial.sql",
    "002_alimentos.sql",
    "003_coach.sql",
    "004_conversas.sql",
    "005_memorias.sql",
    "006_treino.sql",
    "007_minutos_corrida.sql",
    "008_minutos_cardio.sql",
    "009_sessoes.sql",
]

CONVITE = "convite-teste"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "hachibu.db"),
        session_secret="s" * 32,
        invite_code=CONVITE,
        cookie_secure=False,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def make_user(app):
    """Cria um usuário pela API e devolve um TestClient próprio, já logado."""

    def _make(email: str = "a@x.com", senha: str = "senha-forte-1") -> TestClient:
        c = TestClient(app)
        r = c.post("/api/auth/signup", json={"email": email, "senha": senha, "convite": CONVITE})
        assert r.status_code == 201, r.text
        return c

    return _make


@pytest.fixture
def aluno(app, make_user):
    """Usuário logado com o perfil BASE preenchido."""
    from tests.test_metas import BASE

    c = make_user()
    c.put("/api/perfil", json=BASE)
    return c
