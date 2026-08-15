from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    # requires a running Postgres (docker compose up) with the schema applied
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
