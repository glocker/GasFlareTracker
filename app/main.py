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
            FROM facility_status_asof(coalesce(%s,
            (SELECT max(night_date) FROM facility_night)));
        """

    with pool.connection() as conn:
        cur = conn.execute(query, [current_date])

        result = cur.fetchone()

    # psycopg parse column on it's own
    return result[0]


# Start page.
# html=True serves frontend/index.html for "/".
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
