import pytest
from fastapi.testclient import TestClient

import app.main as main
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
    assert body["data_ready"] is True

    if body["features"]:
        feature = body["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["properties"].keys() >= {"name", "kind", "operator", "status"}


def test_get_facilities_filtered_by_country(client: TestClient) -> None:
    resp = client.get("/api/facilities", params={"country": "US"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_ready"] is True
    assert len(body["features"]) > 0

    # v0.1 data is US-only, so any other country is a legitimate empty result
    resp = client.get("/api/facilities", params={"country": "FR"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_ready"] is True
    assert body["features"] == []


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.calls.append((str(query), params))
        return FakeResult([((None, None))])


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def connection(self):
        return self.conn


def test_get_facilities_returns_not_ready_before_pipeline(monkeypatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(main, "pool", FakePool(conn))

    body = main.get_facilities()

    assert body == {
        "type": "FeatureCollection",
        "as_of": None,
        "data_ready": False,
        "features": [],
    }
    assert len(conn.calls) == 1


def test_get_facilities_rejects_malformed_country(client: TestClient) -> None:
    resp = client.get("/api/facilities", params={"country": "usa"})
    assert resp.status_code == 422


def test_get_facilities_outside_loaded_period_is_empty(client: TestClient) -> None:
    # facility_status_asof() always returns every facility
    # when we get date in the future or date with no data - return empty array
    # on UI we show empty view
    resp = client.get("/api/facilities", params={"current_date": "2027-01-01"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["as_of"] == "2027-01-01"
    assert body["data_ready"] is True
    assert body["features"] == []
