from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.db import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool.open()
    yield
    pool.close()


app = FastAPI(title="GasFlareTracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}

@app.get("/api/facilities")
def get_facilities() -> dict:
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
            FROM facility_status;
        """

    with pool.connection() as conn:
        cur = conn.execute(query)

        result = cur.fetchone()

    # psycopg parse column on it's own
    return result[0]
