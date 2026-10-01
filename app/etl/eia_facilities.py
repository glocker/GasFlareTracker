import sys
import time
from dataclasses import dataclass

import httpx
import pandas as pd
from psycopg.types.json import Json

from app.etl.known_coordinates import lookup as lookup_known_coordinates

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a real identifying User-Agent and caps
# requests at 1/second - https://operations.osmfoundation.org/policies/nominatim/
# Replace the contact before running this for real.
USER_AGENT = "GasFlareTracker/0.1 (contact: replace-with-real-email)"
EVENT_YEAR = 2020


@dataclass
class Geocoded:
    lon: float
    lat: float


def _db_pool():
    from app.db import pool

    return pool


def _registry_year(df: pd.DataFrame) -> int | None:
    if "PERIOD" not in df.columns:
        return None

    periods = df["PERIOD"].dropna().astype(str).str.strip().unique()
    if len(periods) != 1 or not periods[0].isdigit():
        return None

    period = int(periods[0])
    return 2000 + period if period < 100 else period


def _registry_limitation_note(registry_year: int | None) -> str:
    if registry_year is None:
        return "EIA registry period unknown; v0.1 events are evaluated for 2020"
    if registry_year == EVENT_YEAR:
        return f"EIA Refinery Capacity Report {registry_year}"
    return (
        f"EIA Refinery Capacity Report {registry_year}; v0.1 events are evaluated for "
        f"{EVENT_YEAR}, so registry and event period may be out of sync"
    )


def _update_registry_provenance(
    conn, ref_id: int, facility_id: int, registry_year: int | None, registry_note: str
) -> None:
    conn.execute(
        """
        UPDATE facility_external_ref
           SET raw = COALESCE(raw, '{}'::jsonb) || %s::jsonb
         WHERE id = %s
        """,
        (Json({"registry_year": registry_year}), ref_id),
    )
    conn.execute(
        """
        UPDATE facility
           SET notes = CASE
               WHEN notes IS NULL OR notes = '' THEN %s
               WHEN position(%s in notes) > 0 THEN notes
               ELSE notes || '; ' || %s
           END
         WHERE id = %s
        """,
        (registry_note, registry_note, registry_note, facility_id),
    )


def _geocode(city: str, state: str, client: httpx.Client) -> Geocoded | None:
    resp = client.get(
        NOMINATIM_URL,
        params={"city": city, "state": state, "country": "USA", "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return Geocoded(lon=float(results[0]["lon"]), lat=float(results[0]["lat"]))


def load(xlsx_path: str) -> int:
    # EIA's Refinery Capacity Report has no coordinates - only
    # CORPORATION/COMPANY_NAME/STATE_NAME/SITE (city). Facilities are
    # geocoded to city center via Nominatim as a v0.1 approximation. City
    # center can be several km off from the actual refinery, which matters
    # against the 3km match_radius_m default - a known gap, not a solved one.
    df = pd.read_excel(xlsx_path, sheet_name=0)
    registry_year = _registry_year(df)
    registry_note = _registry_limitation_note(registry_year)
    facilities = df[["CORPORATION", "COMPANY_NAME", "STATE_NAME", "SITE"]].drop_duplicates()

    cache: dict[tuple[str, str], Geocoded | None] = {}
    inserted = 0

    # Caller owns pool lifecycle (see app/cli.py) - assumed already open here.
    with httpx.Client(timeout=10) as client, _db_pool().connection() as conn:
        for row in facilities.itertuples(index=False):
            external_id = f"{row.CORPORATION}|{row.COMPANY_NAME}|{row.SITE}|{row.STATE_NAME}"
            existing = conn.execute(
                """
                SELECT id, facility_id FROM facility_external_ref
                 WHERE source = 'eia_refcap' AND external_id = %s
                """,
                (external_id,),
            ).fetchone()
            if existing:
                ref_id, facility_id = existing
                _update_registry_provenance(
                    conn, ref_id, facility_id, registry_year, registry_note
                )
                continue

            known = lookup_known_coordinates(row.CORPORATION, row.STATE_NAME, row.SITE)
            if known is not None:
                lon, lat = known
                notes = (
                    f"{row.SITE.title()}, {row.STATE_NAME} - verified flare-stack location; "
                    f"{registry_note}"
                )
            else:
                key = (row.SITE, row.STATE_NAME)
                if key not in cache:
                    cache[key] = _geocode(row.SITE, row.STATE_NAME, client)
                    time.sleep(1)  # Nominatim: max 1 request/second

                geocoded = cache[key]
                if geocoded is None:
                    place = f"{row.COMPANY_NAME} / {row.SITE}, {row.STATE_NAME}"
                    print(f"skipped (geocoding failed): {place}")
                    continue

                lon, lat = geocoded.lon, geocoded.lat
                place = f"{row.SITE.title()}, {row.STATE_NAME}"
                notes = f"{place} - geocoded to city center, not exact; {registry_note}"

            facility_id = conn.execute(
                """
                INSERT INTO facility
                       (name, kind, country_iso2, operator, parent_owner, geom, notes)
                VALUES (%s, 'refinery', 'US', %s, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                RETURNING id
                """,
                (
                    row.COMPANY_NAME.title(),
                    row.COMPANY_NAME.title(),
                    row.CORPORATION.title(),
                    lon,
                    lat,
                    notes,
                ),
            ).fetchone()[0]

            conn.execute(
                """
                INSERT INTO facility_external_ref
                       (facility_id, source, external_id, name_in_src, raw)
                VALUES (%s, 'eia_refcap', %s, %s, %s)
                """,
                (
                    facility_id,
                    external_id,
                    row.COMPANY_NAME,
                    Json({**dict(row._asdict()), "registry_year": registry_year}),
                ),
            )
            inserted += 1

    return inserted


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/refcap26.xlsx"
    pool = _db_pool()
    pool.open()
    try:
        print(f"inserted {load(path)} facilities")
    finally:
        pool.close()
