def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_aplica_migracoes(app, settings):
    from hachibu.db import connect

    nomes = [r["name"] for r in connect(settings.db_path).execute("SELECT name FROM schema_version")]
    assert nomes == ["001_inicial.sql", "002_alimentos.sql", "003_coach.sql", "004_conversas.sql"]
