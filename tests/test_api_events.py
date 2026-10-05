import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app


@pytest.fixture(scope="module")
def client():
    # requires a running Postgres with detect-events already run against it
    # shared across tests: app.main's pool can't be reopened once closed,
    # so each test can't get its own TestClient(app)
    with TestClient(app) as c:
        yield c


def test_get_events_shape(client: TestClient) -> None:
    resp = client.get("/api/events", params={"limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert body["data_ready"] is True
    assert len(body["events"]) <= 5

    if body["events"]:
        event = body["events"][0]
        assert event.keys() >= {
            "id",
            "facility_id",
            "facility_name",
            "facility_kind",
            "facility_operator",
            "facility_lon",
            "facility_lat",
            "kind",
            "start_date",
            "end_date",
            "peak_frp",
            "baseline_frp",
            "score",
            "blind_nights",
        }
        assert event["kind"] in {"spike", "regime_up", "regime_down"}


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
        if "EXISTS (SELECT 1 FROM facility_night)" in str(query):
            return FakeResult([(True,)])
        return FakeResult([({"events": []},)])


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def connection(self):
        return self.conn


def test_get_events_filters_to_latest_detector_version(monkeypatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(main, "pool", FakePool(conn))

    body = main.get_events(limit=25)

    assert body == {"data_ready": True, "events": []}
    sql, params = conn.calls[1]
    assert "WITH current_detector AS" in sql
    assert "FROM detector_version" in sql
    assert "ORDER BY id DESC" in sql
    assert "JOIN current_detector cd ON cd.id = fe.detector_id" in sql
    assert "ST_X(f.geom) AS facility_lon" in sql
    assert "ST_Y(f.geom) AS facility_lat" in sql
    assert params == [None, None, 25]


def test_get_events_rejects_invalid_limit(client: TestClient) -> None:
    resp = client.get("/api/events", params={"limit": 0})
    assert resp.status_code == 422


def test_get_events_sorted_desc_and_date_filtered(client: TestClient) -> None:
    resp = client.get(
        "/api/events",
        params={"date_from": "2020-06-01", "date_to": "2020-07-01"},
    )
    assert resp.status_code == 200
    events = resp.json()["events"]

    dates = [e["start_date"] for e in events]
    assert dates == sorted(dates, reverse=True)
    assert all("2020-06-01" <= d <= "2020-07-01" for d in dates)
