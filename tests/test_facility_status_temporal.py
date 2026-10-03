import os
from datetime import date

import psycopg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")


class ExistingConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class ExistingConnectionPool:
    def __init__(self, connection):
        self.connection = connection

    def connection(self):
        return ExistingConnectionContext(self.connection)


@pytest.fixture
def conn():
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL is required for PostGIS integration test")

    try:
        connection = psycopg.connect(DATABASE_URL)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available: {exc}")

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _insert_temporal_fixture(conn) -> tuple[int, date, date]:
    as_of = date(2020, 6, 15)
    past_seen = date(2020, 5, 1)
    future_seen = date(2020, 6, 16)

    facility_id = conn.execute(
        """
        INSERT INTO facility (name, kind, country_iso2, operator, geom, notes)
        VALUES (
            'Temporal status fixture',
            'refinery',
            'ZZ',
            'Temporal QA',
            ST_SetSRID(ST_MakePoint(-100.0, 30.0), 4326),
            'test fixture'
        )
        RETURNING id
        """
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO facility_night (facility_id, night_date, n_det, frp_sum, frp_max)
        VALUES
            (%s, %s, 1, 10, 10),
            (%s, %s, 1, 1000, 1000)
        """,
        (facility_id, past_seen, facility_id, future_seen),
    )
    return facility_id, as_of, past_seen


def test_facility_status_asof_does_not_see_future_facility_nights(conn) -> None:
    facility_id, as_of, past_seen = _insert_temporal_fixture(conn)

    last_seen, frp_30d_median, frp_365d_median, status = conn.execute(
        """
        SELECT last_seen, frp_30d_median, frp_365d_median, status
          FROM facility_status_asof(%s)
         WHERE id = %s
        """,
        (as_of, facility_id),
    ).fetchone()

    assert last_seen == past_seen
    assert frp_30d_median is None
    assert frp_365d_median == 10
    assert status == "silent"


def test_get_facilities_current_date_does_not_see_future_facility_nights(
    conn, monkeypatch
) -> None:
    _, as_of, _ = _insert_temporal_fixture(conn)

    import app.main as main

    monkeypatch.setattr(main, "pool", ExistingConnectionPool(conn))

    body = main.get_facilities(current_date=as_of, country="ZZ")

    assert body["as_of"] == as_of.isoformat()
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["status"] == "silent"
