import sys
import time
from dataclasses import dataclass

import httpx
import pandas as pd
from psycopg.types.json import Json

from app.db import pool
from app.etl.known_coordinates import lookup as lookup_known_coordinates

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a real identifying User-Agent and caps
# requests at 1/second - https://operations.osmfoundation.org/policies/nominatim/
# Replace the contact before running this for real.
USER_AGENT = "GasFlareTracker/0.1 (contact: replace-with-real-email)"


@dataclass
class Geocoded:
    lon: float
    lat: float


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
    facilities = df[["CORPORATION", "COMPANY_NAME", "STATE_NAME", "SITE"]].drop_duplicates()

    cache: dict[tuple[str, str], Geocoded | None] = {}
    inserted = 0

    # Caller owns pool lifecycle (see app/cli.py) - assumed already open here.
    with httpx.Client(timeout=10) as client, pool.connection() as conn:
        for row in facilities.itertuples(index=False):
            external_id = f"{row.CORPORATION}|{row.COMPANY_NAME}|{row.SITE}|{row.STATE_NAME}"
            exists = conn.execute(
                """
                SELECT 1 FROM facility_external_ref
                 WHERE source = 'eia_refcap' AND external_id = %s
                """,
                (external_id,),
            ).fetchone()
            if exists:
                continue

            known = lookup_known_coordinates(row.CORPORATION, row.STATE_NAME, row.SITE)
            if known is not None:
                lon, lat = known
                notes = f"{row.SITE.title()}, {row.STATE_NAME} - verified flare-stack location"
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
                notes = f"{place} - geocoded to city center, not exact"

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
                (facility_id, external_id, row.COMPANY_NAME, Json(dict(row._asdict()))),
            )
            inserted += 1

    return inserted


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/refcap26.xlsx"
    pool.open()
    try:
        print(f"inserted {load(path)} facilities")
    finally:
        pool.close()
