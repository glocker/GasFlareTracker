import os
from datetime import UTC, date, datetime

import psycopg
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL")


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


def test_match_detections_assigns_port_arthur_detection_to_nearest_facility(conn) -> None:
    motiva_id = conn.execute(
        """
        INSERT INTO facility (name, kind, country_iso2, operator, geom, match_radius_m, notes)
        VALUES (
            'Port Arthur Motiva fixture',
            'refinery',
            'US',
            'Saudi Aramco',
            ST_SetSRID(ST_MakePoint(-93.9510, 29.8886), 4326),
            9000,
            'test fixture'
        )
        RETURNING id
        """
    ).fetchone()[0]
    valero_id = conn.execute(
        """
        INSERT INTO facility (name, kind, country_iso2, operator, geom, match_radius_m, notes)
        VALUES (
            'Port Arthur Valero fixture',
            'refinery',
            'US',
            'Valero',
            ST_SetSRID(ST_MakePoint(-93.9634, 29.8654), 4326),
            9000,
            'test fixture'
        )
        RETURNING id
        """
    ).fetchone()[0]

    detection_id, night_date = conn.execute(
        """
        INSERT INTO detection (
            acq_ts,
            night_date,
            geom,
            frp,
            daynight,
            confidence,
            satellite,
            source
        )
        VALUES (
            %s,
            %s,
            ST_SetSRID(ST_MakePoint(-93.9512, 29.8884), 4326),
            42.0,
            'N',
            'n',
            'N',
            'TEST'
        )
        RETURNING id, night_date
        """,
        (datetime(2020, 6, 15, 6, 12, tzinfo=UTC), date(2020, 6, 14)),
    ).fetchone()

    matched = conn.execute(
        "SELECT match_detections(%s, %s, true)", (date(2020, 6, 14), date(2020, 6, 15))
    ).fetchone()[0]
    facility_id, dist_m = conn.execute(
        """
        SELECT facility_id, dist_m
          FROM detection
         WHERE id = %s AND night_date = %s
        """,
        (detection_id, night_date),
    ).fetchone()

    assert matched >= 1
    assert facility_id == motiva_id
    assert facility_id != valero_id
    assert dist_m < 50
