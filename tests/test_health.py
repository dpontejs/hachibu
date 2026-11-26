def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_aplica_migracoes(app):
    nomes = [r["name"] for r in app.state.db.execute("SELECT name FROM schema_version")]
    assert nomes == ["001_inicial.sql"]
