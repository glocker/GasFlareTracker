import csv
import io
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from psycopg import errors as pg_errors

from app.config import FIRMS_MAP_KEY
from app.db import pool
from app.etl.night_date import night_date, parse_acq_time

# The Area API caps a single request at 5 days (verified against the live
# API docs - older docs floating around say 10, that's stale).
DAY_RANGE = 5
DEFAULT_SOURCES = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]
AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{day_range}/{date}"
CSV_HEADER = "latitude,longitude"  # real header always starts with this; an
# error response (bad key, rate limit) comes back as plain text instead

# Politeness delay between requests. At ~4400 requests for a full 2020-2021
# US backfill this keeps the run well under the 5000 tx/10min key limit
# without needing to track a rolling counter.
REQUEST_DELAY_S = 0.35
MAX_ATTEMPTS = 3


@dataclass
class Region:
    id: int
    name: str
    west: float
    south: float
    east: float
    north: float


def _regions(conn) -> list[Region]:
    rows = conn.execute(
        """
        SELECT id, name, ST_XMin(bbox), ST_YMin(bbox), ST_XMax(bbox), ST_YMax(bbox)
          FROM fetch_region
         WHERE active
         ORDER BY id
        """
    ).fetchall()
    return [Region(*row) for row in rows]


def _date_windows(p_from: date, p_to: date):
    # window_start, day_range pairs covering [p_from, p_to)
    #  the last window is shortened to fit instead of overshooting p_to
    cur = p_from
    while cur < p_to:
        remaining = (p_to - cur).days
        span = min(DAY_RANGE, remaining)
        yield cur, span
        cur += timedelta(days=span)


def _fetch_csv(source: str, bbox: str, start: date, span: int, client: httpx.Client) -> str:
    url = AREA_URL.format(
        key=FIRMS_MAP_KEY, source=source, bbox=bbox, day_range=span, date=start.isoformat()
    )
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except (httpx.HTTPError,) as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"FIRMS request failed after {MAX_ATTEMPTS} attempts: {last_error}")


def _parse_rows(csv_text: str, source: str) -> list[dict]:
    if not csv_text.startswith(CSV_HEADER):
        # FIRMS returns plain-text errors (bad key, throttling) with 200
        # status code instead of an HTTP error code. This is the only reliable
        # way to detect it.
        raise ValueError(csv_text.strip()[:500] or "empty response")

    rows = []
    for r in csv.DictReader(io.StringIO(csv_text)):
        lon, lat = float(r["longitude"]), float(r["latitude"])
        acq_date = date.fromisoformat(r["acq_date"])
        rows.append(
            {
                "acq_ts": datetime.combine(
                    acq_date, parse_acq_time(r["acq_time"]), tzinfo=timezone.utc
                ),
                "night_date": night_date(acq_date, r["acq_time"], lon),
                "lon": lon,
                "lat": lat,
                "frp": float(r["frp"]) if r.get("frp") else None,
                "bright_ti4": float(r["bright_ti4"]) if r.get("bright_ti4") else None,
                "bright_ti5": float(r["bright_ti5"]) if r.get("bright_ti5") else None,
                "daynight": r["daynight"],
                "confidence": r["confidence"],
                "satellite": r["satellite"],
                "source": source,
                "scan": float(r["scan"]) if r.get("scan") else None,
                "track": float(r["track"]) if r.get("track") else None,
            }
        )
    return rows


_INSERT_DETECTIONS = """
    INSERT INTO detection
           (acq_ts, night_date, geom, frp, bright_ti4, bright_ti5,
            daynight, confidence, satellite, source, scan, track, fetch_id)
    VALUES (%(acq_ts)s, %(night_date)s,
            ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
            %(frp)s, %(bright_ti4)s, %(bright_ti5)s, %(daynight)s, %(confidence)s,
            %(satellite)s, %(source)s, %(scan)s, %(track)s, %(fetch_id)s)
    ON CONFLICT (satellite, acq_ts, geom, night_date) DO NOTHING
"""


def _already_fetched(conn, region_id: int, source: str, day_from: date, day_to: date) -> bool:
    return (
        conn.execute(
            """
            SELECT 1 FROM fetch_log
             WHERE region_id = %s AND source = %s AND day_from = %s AND day_to = %s
               AND status = 'ok'
             LIMIT 1
            """,
            (region_id, source, day_from, day_to),
        ).fetchone()
        is not None
    )


def run(p_from: date, p_to: date, sources: list[str] | None = None) -> dict:
    sources = sources or DEFAULT_SOURCES
    stats = {"windows": 0, "rows": 0, "errors": 0, "skipped": 0}

    with pool.connection() as conn:
        regions = _regions(conn)

    total_windows = len(regions) * len(sources) * len(list(_date_windows(p_from, p_to)))
    done = 0

    with httpx.Client() as client:
        for region in regions:
            bbox = f"{region.west},{region.south},{region.east},{region.north}"
            for source in sources:
                for start, span in _date_windows(p_from, p_to):
                    day_to = start + timedelta(days=span)
                    done += 1

                    with pool.connection() as conn:
                        if _already_fetched(conn, region.id, source, start, day_to):
                            stats["skipped"] += 1
                            continue

                    try:
                        csv_text = _fetch_csv(source, bbox, start, span, client)
                        rows = _parse_rows(csv_text, source)
                        error = None
                    except Exception as exc:  # noqa: BLE001 - logged into fetch_log, not raised
                        rows = []
                        error = str(exc)

                    with pool.connection() as conn:
                        log_id = conn.execute(
                            """
                            INSERT INTO fetch_log
                                   (region_id, source, day_from, day_to, n_rows, status, error)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                region.id,
                                source,
                                start,
                                day_to,
                                len(rows),
                                "error" if error else "ok",
                                error,
                            ),
                        ).fetchone()[0]

                        if rows:
                            for r in rows:
                                r["fetch_id"] = log_id
                            try:
                                with conn.cursor() as cur:
                                    cur.executemany(_INSERT_DETECTIONS, rows)
                            except pg_errors.Error as exc:
                                # rollback also discards the fetch_log insert above (same
                                # transaction) - relog the window as failed from scratch
                                conn.rollback()
                                error = str(exc)
                                conn.execute(
                                    """
                                    INSERT INTO fetch_log
                                           (region_id, source, day_from, day_to, n_rows, status, error)
                                    VALUES (%s, %s, %s, %s, %s, 'error', %s)
                                    """,
                                    (region.id, source, start, day_to, len(rows), error[:500]),
                                )

                    if error:
                        stats["errors"] += 1
                        print(f"[{done}/{total_windows}] {region.name} {source} {start}: ERROR {error[:200]}")
                    else:
                        stats["rows"] += len(rows)
                        stats["windows"] += 1
                        if done % 20 == 0 or len(rows) > 0:
                            print(
                                f"[{done}/{total_windows}] {region.name} {source} {start}..{day_to}: "
                                f"{len(rows)} rows"
                            )

                    time.sleep(REQUEST_DELAY_S)

    return stats


if __name__ == "__main__":
    import sys

    p_from = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2020, 1, 1)
    p_to = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2022, 1, 1)
    pool.open()
    try:
        result = run(p_from, p_to)
        print(result)
    finally:
        pool.close()
