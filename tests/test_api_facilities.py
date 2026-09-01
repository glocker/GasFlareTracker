import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    # requires a running Postgres with `facility_status` populated
    with TestClient(app) as c:
        yield c


def test_get_facilities_shape(client: TestClient) -> None:
    resp = client.get("/api/facilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert "as_of" in body

    if body["features"]:
        feature = body["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"].keys() >= {"name", "kind", "operator", "status"}


def test_get_facilities_filtered_by_country(client: TestClient) -> None:
    resp = client.get("/api/facilities", params={"country": "US"})
    assert resp.status_code == 200
    assert len(resp.json()["features"]) > 0

    # v0.1 data is US-only, so any other country is a legitimate empty result
    resp = client.get("/api/facilities", params={"country": "FR"})
    assert resp.status_code == 200
    assert resp.json()["features"] == []


def test_get_facilities_rejects_malformed_country(client: TestClient) -> None:
    resp = client.get("/api/facilities", params={"country": "usa"})
    assert resp.status_code == 422
