from datetime import date
from typing import Any

pool: Any | None = None


def _db_pool():
    global pool
    if pool is None:
        from app.db import pool as db_pool

        pool = db_pool
    return pool


def run(
    p_from: date,
    p_to: date,
    cluster_distance_m: int = 3000,
    limit: int = 50,
) -> dict:
    with _db_pool().connection() as conn:
        no_detections = conn.execute(
            """
            SELECT f.id,
                   f.name,
                   f.operator,
                   f.parent_owner,
                   f.notes
              FROM facility f
              LEFT JOIN facility_night fn
                ON fn.facility_id = f.id
               AND fn.night_date >= %s
               AND fn.night_date <  %s
               AND fn.n_det > 0
             WHERE fn.facility_id IS NULL
             ORDER BY f.name, f.id
             LIMIT %s
            """,
            (p_from, p_to, limit),
        ).fetchall()

        close_clusters = conn.execute(
            """
            SELECT f1.id,
                   f1.name,
                   f1.operator,
                   f2.id,
                   f2.name,
                   f2.operator,
                   ST_Distance(f1.geom::geography, f2.geom::geography) AS distance_m
              FROM facility f1
              JOIN facility f2
                ON f1.id < f2.id
               AND ST_DWithin(f1.geom::geography, f2.geom::geography, %s)
             ORDER BY distance_m, f1.id, f2.id
             LIMIT %s
            """,
            (cluster_distance_m, limit),
        ).fetchall()

    return {
        "period": {"from": p_from.isoformat(), "to": p_to.isoformat()},
        "no_detection_facilities": [
            {
                "id": row[0],
                "name": row[1],
                "operator": row[2],
                "parent_owner": row[3],
                "notes": row[4],
            }
            for row in no_detections
        ],
        "close_clusters": [
            {
                "facility_a": {"id": row[0], "name": row[1], "operator": row[2]},
                "facility_b": {"id": row[3], "name": row[4], "operator": row[5]},
                "distance_m": float(row[6]),
            }
            for row in close_clusters
        ],
    }
