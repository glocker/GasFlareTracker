# Hand-verified flare-stack coordinates for a handful of major Gulf Coast
# refineries (from prior FIRMS exploration in ../firms/firms_check.py),
# checked against the current EIA Refinery Capacity Report by corporation +
# state + site. Takes priority over Nominatim city-level geocoding in
# eia_facilities.py - these are actual facility locations, not city centers.
#
# "site" must match EIA's SITE column exactly (uppercase). Note Marathon's
# Texas City refinery is now listed as "GALVESTON BAY" in the 2026 report,
# not "TEXAS CITY" (that's Valero's separate, unrelated refinery there).
KNOWN_COORDINATES = [
    {"corporation_contains": "SAUDI ARAMCO", "state": "Texas", "site": "PORT ARTHUR",
     "lat": 29.8886, "lon": -93.9510},
    {"corporation_contains": "VALERO ENERGY CORP", "state": "Texas", "site": "PORT ARTHUR",
     "lat": 29.8654, "lon": -93.9634},
    {"corporation_contains": "EXXON MOBIL CORP", "state": "Texas", "site": "BAYTOWN",
     "lat": 29.7450, "lon": -95.0012},
    {"corporation_contains": "MARATHON PETROLEUM CORP", "state": "Texas", "site": "GALVESTON BAY",
     "lat": 29.3788, "lon": -94.9297},
    {"corporation_contains": None, "state": "Texas", "site": "DEER PARK",
     "lat": 29.7128, "lon": -95.1275},
    {"corporation_contains": "SHELL PLC", "state": "Louisiana", "site": "NORCO",
     "lat": 29.9955, "lon": -90.4099},
    {"corporation_contains": "MARATHON PETROLEUM CORP", "state": "Louisiana", "site": "GARYVILLE",
     "lat": 30.0625, "lon": -90.5927},
    {"corporation_contains": "VALERO ENERGY CORP", "state": "Louisiana", "site": "MERAUX",
     "lat": 29.9337, "lon": -89.9445},
]


def lookup(corporation: str, state: str, site: str) -> tuple[float, float] | None:
    for entry in KNOWN_COORDINATES:
        if entry["state"] != state or entry["site"] != site:
            continue
        if entry["corporation_contains"] and entry["corporation_contains"] not in corporation:
            continue
        return entry["lon"], entry["lat"]
    return None
