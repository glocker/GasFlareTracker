import pytest
from fastapi.testclient import TestClient

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
    assert len(body["events"]) <= 5

    if body["events"]:
        event = body["events"][0]
        assert event.keys() >= {
            "id",
            "facility_id",
            "facility_name",
            "kind",
            "start_date",
            "end_date",
            "peak_frp",
            "baseline_frp",
            "score",
            "blind_nights",
        }
        assert event["kind"] in {"spike", "regime_up", "regime_down"}


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
