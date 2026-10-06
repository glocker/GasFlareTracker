from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Query
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
def get_facilities(
    current_date: date | None = None,
    # Value is ISO 3166-1 alpha-2 code, matching facility.country_iso2
    country: str | None = Query(default=None, pattern="^[A-Z]{2}$"),
) -> dict:
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
            FROM facility_status_asof(%s)
            -- COALESCE against country_iso2 makes a NULL filter a no-op
            WHERE country_iso2 = COALESCE(%s, country_iso2);
        """

    with pool.connection() as conn:
        loaded_period = conn.execute(
            "SELECT min(night_date), max(night_date) FROM facility_night"
        ).fetchone()
        if loaded_period is None:
            raise RuntimeError("facility_night period query did not return a row")
        loaded_from, loaded_to = loaded_period

        if loaded_from is None or loaded_to is None:
            return {
                "type": "FeatureCollection",
                "as_of": None,
                "data_ready": False,
                "features": [],
            }

        if current_date is None:
            # no date given, use latest night we've got
            current_date = loaded_to

        # facility_status_asof() always returns every facility. Outside the
        # loaded period is a real empty result, not a pipeline-not-ready state.
        if not (loaded_from <= current_date <= loaded_to):
            return {
                "type": "FeatureCollection",
                "as_of": current_date,
                "data_ready": True,
                "features": [],
            }

        cur = conn.execute(query, [current_date, current_date, country])

        result = cur.fetchone()

    if result is None:
        raise RuntimeError("facility query did not return a GeoJSON collection")

    # psycopg parses the JSON column on its own
    geojson = result[0]
    geojson["data_ready"] = True
    return geojson


@app.get("/api/events")
def get_events(
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict:
    # Plain JSON, not GeoJSON - events aren't map geometry, just a feed list.
    # date_from/date_to/limit are already here even without pagination in the
    # UI yet, so a full-archive view later won't need new query params.
    query = """
            SELECT json_build_object(
                'events', COALESCE(json_agg(row_to_json(e)), '[]'::json)
            ) AS events_collection
            FROM (
                WITH current_detector AS (
                    SELECT id
                      FROM detector_version
                     ORDER BY id DESC
                     LIMIT 1
                )
                SELECT fe.id,
                       fe.facility_id,
                       f.name AS facility_name,
                       f.kind AS facility_kind,
                       f.operator AS facility_operator,
                       ST_X(f.geom) AS facility_lon,
                       ST_Y(f.geom) AS facility_lat,
                       fe.kind,
                       fe.start_date,
                       fe.end_date,
                       fe.peak_frp,
                       fe.baseline_frp,
                       fe.score,
                       fe.blind_nights
                  FROM flare_event fe
                  JOIN current_detector cd ON cd.id = fe.detector_id
                  JOIN facility f ON f.id = fe.facility_id
                 -- COALESCE against fe.start_date makes a NULL bound a no-op
                 WHERE fe.start_date >= COALESCE(%s, fe.start_date)
                   AND fe.start_date <= COALESCE(%s, fe.start_date)
                 ORDER BY fe.start_date DESC
                 LIMIT %s
            ) e;
        """

    with pool.connection() as conn:
        data_ready = conn.execute(
            """
            SELECT EXISTS (SELECT 1 FROM facility_night)
               AND EXISTS (SELECT 1 FROM detector_version)
            """
        ).fetchone()
        if data_ready is None:
            raise RuntimeError("event readiness query did not return a row")
        if not data_ready[0]:
            return {"data_ready": False, "events": []}

        cur = conn.execute(query, [date_from, date_to, limit])
        result = cur.fetchone()

    if result is None:
        raise RuntimeError("event query did not return an events collection")

    events = result[0]
    events["data_ready"] = True
    return events


# Start page.
# html=True serves frontend/index.html for "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
