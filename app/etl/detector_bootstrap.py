from psycopg.types.json import Json

from app.db import pool

# Mirrors the elevated/reduced thresholds already used by the facility_status
# view (db/schema.sql) so "spike" in flare_event lines up with "elevated" on
# the map instead of drifting apart as two independently-tuned numbers.
DEFAULT_PARAMS = {
    "spike_multiplier": 2.0,
    "reduced_multiplier": 0.5,
    "baseline_window_days": 365,
    "recent_window_days": 30,
    # how many days an above/below episode must last before it stops being a
    # "spike" and becomes a "regime_up"/"regime_down" (see event_detector.py)
    "event_min_duration_days": 14,
    # consecutive back-to-normal nights required to close an episode - avoids
    # one noisy night splitting a single episode into two
    "event_close_hysteresis_nights": 3,
}


def run(name: str = "v0.1-baseline") -> int:
    # Caller owns pool lifecycle (see app/cli.py) - assumed already open here.
    with pool.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO detector_version (name, params)
            VALUES (%s, %s)
            RETURNING id
            """,
            (name, Json(DEFAULT_PARAMS)),
        ).fetchone()
        return row[0]


if __name__ == "__main__":
    pool.open()
    try:
        print(f"inserted detector_version id={run()}")
    finally:
        pool.close()
