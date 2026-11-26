from fastapi.testclient import TestClient

from hachibu.app import create_app
from hachibu.config import Settings


def test_healthz(tmp_path):
    client = TestClient(
        create_app(
            Settings(
                db_path=str(tmp_path / "t.db"),
                session_secret="s" * 32,
                invite_code="convite",
                cookie_secure=False,
            )
        )
    )
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
