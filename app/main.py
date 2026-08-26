from contextlib import asynccontextmanager
from pathlib import Path
from datetime import date

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import pool

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool.open()
    yield
    pool.close()


app = FastAPI(title="GasFlareTracker", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}

@app.get("/api/facilities")
def get_facilities(current_date: date | None = None) -> dict:
    # Get valid GeoJSON in FeatureCollection
    query = """
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'as_of', %s,
                'features', COALESCE(
                    json_agg(
                    -- use COALESCE to return empty array if facility_status is empty
                    -- and json_agg returns "features":null
                        json_build_object(
                            'type',       'Feature',
                            'id',         id,
                            'geometry',   ST_AsGeoJSON(geom)::json,
                            'properties', json_build_object(
                                'name', name,
                                'kind', kind,
                                'operator', operator,
                                'status', status)
                        )
                    ),
                    '[]'::json
                )
            ) as geojson_collection
            FROM facility_status_asof(%s);
        """

    with pool.connection() as conn:
        if current_date is None:
            # no date given, use latest night we've got
            current_date = conn.execute("SELECT max(night_date) FROM facility_night").fetchone()[0]

        cur = conn.execute(query, [current_date, current_date])

        result = cur.fetchone()

    # psycopg parse column on it's own
    return result[0]


@app.get("/api/events")
def get_events(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 1000,
) -> dict:
    # Plain JSON, not GeoJSON - events aren't map geometry, just a feed list.
    # date_from/date_to/limit are already here even without pagination in the
    # UI yet, so a full-archive view later won't need new query params.
    query = """
            SELECT json_build_object(
                'events', COALESCE(json_agg(row_to_json(e)), '[]'::json)
            ) AS events_collection
            FROM (
                SELECT fe.id,
                       fe.facility_id,
                       f.name AS facility_name,
                       fe.kind,
                       fe.start_date,
                       fe.end_date,
                       fe.peak_frp,
                       fe.baseline_frp,
                       fe.score,
                       fe.blind_nights
                  FROM flare_event fe
                  JOIN facility f ON f.id = fe.facility_id
                 -- COALESCE against fe.start_date makes a NULL bound a no-op
                 WHERE fe.start_date >= COALESCE(%s, fe.start_date)
                   AND fe.start_date <= COALESCE(%s, fe.start_date)
                 ORDER BY fe.start_date DESC
                 LIMIT %s
            ) e;
        """

    with pool.connection() as conn:
        cur = conn.execute(query, [date_from, date_to, limit])
        result = cur.fetchone()

    return result[0]


# Start page.
# html=True serves frontend/index.html for "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
