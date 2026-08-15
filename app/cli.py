import argparse

from app.db import pool
from app.etl import detector_bootstrap, eia_facilities, fetch_regions


def main() -> None:
    parser = argparse.ArgumentParser(prog="gasflaretracker")
    sub = parser.add_subparsers(dest="command", required=True)

    load_facilities = sub.add_parser("load-facilities", help="Load EIA Refinery Capacity Report")
    load_facilities.add_argument("xlsx_path", nargs="?", default="data/refcap26.xlsx")

    build_regions = sub.add_parser("build-fetch-regions", help="Cluster facilities into regions")
    build_regions.add_argument("--clusters", type=int, default=15)

    sub.add_parser("bootstrap-detector", help="Insert the initial detector_version row")

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
    finally:
        pool.close()


if __name__ == "__main__":
    main()
