import argparse
import json
from datetime import date

from app.db import pool
from app.etl import (
    coordinate_qa,
    detector_bootstrap,
    eia_facilities,
    event_detector,
    fetch_regions,
    firms_fetch,
)


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def log_event(event: str, command: str, **fields) -> None:
    print(
        json.dumps(
            {"event": event, "command": command, **fields},
            default=_json_default,
            ensure_ascii=False,
        ),
        flush=True,
    )


def _command_context(args: argparse.Namespace) -> dict:
    fields = {}
    for name in (
        "date_from",
        "date_to",
        "sources",
        "xlsx_path",
        "clusters",
        "force_rematch",
        "concurrently",
        "detector_id",
        "cluster_distance_m",
        "limit",
    ):
        if hasattr(args, name):
            fields[name] = getattr(args, name)
    return fields


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

    match_detections = sub.add_parser(
        "match-detections", help="Attach detections to the nearest facility"
    )
    match_detections.add_argument(
        "--from", dest="date_from", required=True, type=date.fromisoformat
    )
    match_detections.add_argument("--to", dest="date_to", required=True, type=date.fromisoformat)
    match_detections.add_argument(
        "--force-rematch",
        action="store_true",
        help="Clear existing matches in date range before matching again",
    )

    rebuild_nights = sub.add_parser(
        "rebuild-facility-nights", help="Rebuild nightly facility rollups from matched detections"
    )
    rebuild_nights.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    rebuild_nights.add_argument("--to", dest="date_to", required=True, type=date.fromisoformat)

    coordinate_qa_parser = sub.add_parser(
        "coordinate-qa",
        help="Report facilities with no detections and close facility clusters for coordinate QA",
    )
    coordinate_qa_parser.add_argument(
        "--from", dest="date_from", required=True, type=date.fromisoformat
    )
    coordinate_qa_parser.add_argument(
        "--to", dest="date_to", required=True, type=date.fromisoformat
    )
    coordinate_qa_parser.add_argument("--cluster-distance-m", type=int, default=3000)
    coordinate_qa_parser.add_argument("--limit", type=int, default=50)

    refresh_status = sub.add_parser("refresh-status", help="Refresh facility_status view")
    refresh_status.add_argument(
        "--concurrently",
        action="store_true",
        help="Refresh without blocking readers; requires view to be populated already",
    )

    # Flare event detector
    detect_events = sub.add_parser(
        "detect-events", help="Compare facility_night to baseline, write flare_event rows"
    )
    detect_events.add_argument("--from", dest="date_from", required=True, type=date.fromisoformat)
    detect_events.add_argument("--to", dest="date_to", required=True, type=date.fromisoformat)
    detect_events.add_argument("--detector-id", type=int, default=None)

    args = parser.parse_args()

    context = _command_context(args)
    log_event("start", args.command, **context)

    pool_opened = False
    try:
        # Opened once here, not inside each command: etl functions can be
        # chained in one process this way without a closed-pool reopen crash
        pool.open()
        pool_opened = True
        if args.command == "load-facilities":
            inserted = eia_facilities.load(args.xlsx_path)
            log_event("success", args.command, **context, inserted_facilities=inserted)
        elif args.command == "build-fetch-regions":
            inserted = fetch_regions.run(args.clusters)
            log_event("success", args.command, **context, inserted_fetch_regions=inserted)
        elif args.command == "bootstrap-detector":
            detector_id = detector_bootstrap.run()
            log_event("success", args.command, **context, detector_id=detector_id)
        elif args.command == "fetch-firms":
            stats = firms_fetch.run(args.date_from, args.date_to, args.sources)
            log_event("success", args.command, **context, **stats)
        elif args.command == "match-detections":
            with pool.connection() as conn:
                row = conn.execute(
                    "SELECT match_detections(%s, %s, %s)",
                    (args.date_from, args.date_to, args.force_rematch),
                ).fetchone()
                conn.commit()
            matched_rows = row[0]
            log_event("success", args.command, **context, matched_rows=matched_rows)
        elif args.command == "rebuild-facility-nights":
            with pool.connection() as conn:
                conn.execute(
                    "SELECT rebuild_facility_nights(%s, %s)", (args.date_from, args.date_to)
                )
                rebuilt_rows = conn.execute(
                    """
                    SELECT count(*)
                      FROM facility_night
                     WHERE night_date >= %s
                       AND night_date <  %s
                    """,
                    (args.date_from, args.date_to),
                ).fetchone()[0]
                conn.commit()
            log_event("success", args.command, **context, rebuilt_rows=rebuilt_rows)
        elif args.command == "coordinate-qa":
            report = coordinate_qa.run(
                args.date_from, args.date_to, args.cluster_distance_m, args.limit
            )
            log_event(
                "success",
                args.command,
                **context,
                no_detection_facilities=len(report["no_detection_facilities"]),
                close_clusters=len(report["close_clusters"]),
                report=report,
            )
        elif args.command == "refresh-status":
            statement = "REFRESH MATERIALIZED VIEW facility_status"
            if args.concurrently:
                statement = "REFRESH MATERIALIZED VIEW CONCURRENTLY facility_status"
            with pool.connection() as conn:
                old_autocommit = conn.autocommit
                try:
                    conn.autocommit = args.concurrently
                    conn.execute(statement)
                    if not args.concurrently:
                        conn.commit()
                finally:
                    conn.autocommit = old_autocommit
            log_event("success", args.command, **context, refreshed_view="facility_status")
        elif args.command == "detect-events":
            n = event_detector.run(args.date_from, args.date_to, args.detector_id)
            log_event("success", args.command, **context, upserted_events=n)
    except Exception as exc:
        log_event("failure", args.command, **context, error=type(exc).__name__, message=str(exc))
        raise
    finally:
        if pool_opened:
            pool.close()


if __name__ == "__main__":
    main()
