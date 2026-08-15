from app.db import pool

# Padding around each cluster's bounding box, in meters. Detections can land
# up to match_radius_m from a facility and still be matched to it, so the
# fetch box has to be at least that wide, plus slack for facilities near the
# cluster's own edge.
PAD_METERS = 20_000


def run(n_clusters: int = 15) -> int:
    # Caller owns pool lifecycle (see app/cli.py) - assumed already open here.
    with pool.connection() as conn:
        conn.execute("DELETE FROM fetch_region WHERE name LIKE 'auto-%'")
        cur = conn.execute(
            """
            WITH clustered AS (
                SELECT id, geom,
                       ST_ClusterKMeans(geom, %(k)s) OVER () AS cluster_id
                FROM facility
            )
            INSERT INTO fetch_region (name, bbox)
            SELECT 'auto-' || cluster_id,
                   ST_Envelope(ST_Buffer(ST_Collect(geom)::geography, %(pad)s)::geometry)
              FROM clustered
             GROUP BY cluster_id
            RETURNING id
            """,
            {"k": n_clusters, "pad": PAD_METERS},
        )
        return len(cur.fetchall())


if __name__ == "__main__":
    pool.open()
    try:
        print(f"inserted {run()} fetch_region rows")
    finally:
        pool.close()
