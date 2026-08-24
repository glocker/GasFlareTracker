import argparse
from datetime import date

from app.db import pool
from app.etl import detector_bootstrap, eia_facilities, event_detector, fetch_regions, firms_fetch


def main() -> None:
    parser = argparse.ArgumentParser(prog="gasflaretracker")
    sub = parser.add_subparsers(dest="command", required=True)

    load_facilities = sub.add_parser("load-facilities", help="Load EIA Refinery Capacity Report")
    load_facilities.add_argument("xlsx_path", nargs="?", default="data/refcap26.xlsx")

    build_regions = sub.add_parser("build-fetch-regions", help="Cluster facilities into regions")
    build_regions.add_argument("--clusters", type=int, default=15)

    sub.add_parser("bootstrap-detector", help="Insert the initial detector_version row")

    fetch_firms = sub.add_parser("fetch-firms", help="Download FIRMS detections into `detection`")
    fetch_firms.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    fetch_firms.add_argument("--to", dest="date_to", required=True, type=date.fromisoformat)
    fetch_firms.add_argument("--sources", nargs="+", default=None)

    # Flare event detector
    detect_events = sub.add_parser(
        "detect-events", help="Compare facility_night to baseline, write flare_event rows"
    )
    detect_events.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    detect_events.add_argument("--to", dest="date_to", required=True, type=date.fromisoformat)
    detect_events.add_argument("--detector-id", type=int, default=None)

    args = parser.parse_args()

    # Opened once here, not inside each command: the etl functions can be
    # chained in one process this way without a closed-pool reopen crash.
    pool.open()
    try:
        if args.command == "load-facilities":
            print(f"inserted {eia_facilities.load(args.xlsx_path)} facilities")
        elif args.command == "build-fetch-regions":
            print(f"inserted {fetch_regions.run(args.clusters)} fetch_region rows")
        elif args.command == "bootstrap-detector":
            print(f"inserted detector_version id={detector_bootstrap.run()}")
        elif args.command == "fetch-firms":
            print(firms_fetch.run(args.date_from, args.date_to, args.sources))
        elif args.command == "detect-events":
            n = event_detector.run(args.date_from, args.date_to, args.detector_id)
            print(f"inserted/updated {n} flare_event rows")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
