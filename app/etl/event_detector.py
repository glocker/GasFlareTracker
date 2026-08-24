from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from app.db import pool

# No DB access below - kept pure so state machine (episode grouping,
# delay, spike vs regime) can be unit tested without live Postgres,
# same idea as night_date() in night_date.py


@dataclass(frozen=True)
class NightRecord:
    night_date: date
    frp_sum: float
    observable: bool | None


@dataclass(frozen=True)
class EventDraft:
    kind: str  # spike | regime_up | regime_down
    start_date: date
    end_date: date | None  # None = still ongoing
    peak_frp: float
    baseline_frp: float
    score: float
    blind_nights: int


def _window_median(by_date: dict[date, NightRecord], start: date, end: date) -> float | None:
    values = [r.frp_sum for d, r in by_date.items() if start <= d <= end]
    return median(values) if values else None


def compute_events(
    nights: list[NightRecord],
    params: dict,
    eval_from: date,
    eval_to: date,
) -> list[EventDraft]:
    """
    Walks one facility's nightly history and groups consecutive nights where
    recent FRP is way above or below baseline into spike/regime_up/regime_down
    events

    @param nights - full history, needs at least baseline_window_days of
      lead in before eval_from or earliest nights won't have baseline
    @param params - detector_version.params: spike_multiplier, reduced_multiplier,
      baseline_window_days, recent_window_days, event_min_duration_days,
      event_close_delay_nights
    @param eval_from - first night to evaluate (inclusive)
    @param eval_to - night to stop at (exclusive)
    """
    by_date = {r.night_date: r for r in nights}
    recent_days = params["recent_window_days"]
    baseline_days = params["baseline_window_days"]
    spike_mult = params["spike_multiplier"]
    reduced_mult = params["reduced_multiplier"]
    min_duration = params["event_min_duration_days"]
    delay = params["event_close_delay_nights"]

    events: list[EventDraft] = []
    episode: dict | None = None

    def finalize(end_date: date | None) -> None:
        nonlocal episode
        assert episode is not None  # only called from inside an active episode
        start = episode["start_date"]
        last = episode["last_in_state_date"]
        duration_days = (last - start).days + 1
        kind = (
            "spike"
            if duration_days < min_duration
            else ("regime_up" if episode["direction"] == "above" else "regime_down")
        )
        # observable=False means we know we didn't see facility that
        # night, not just "no detection" - quiet night isn't a blind one
        blind_nights = 0
        d = start
        while d <= last:
            rec = by_date.get(d)
            if rec is not None and rec.observable is False:
                blind_nights += 1
            d += timedelta(days=1)
        baseline = episode["baseline_frp"]
        events.append(
            EventDraft(
                kind=kind,
                start_date=start,
                end_date=end_date,
                peak_frp=episode["peak_frp"],
                baseline_frp=baseline,
                score=(episode["peak_frp"] / baseline) if baseline else 0.0,
                blind_nights=blind_nights,
            )
        )
        episode = None

    t = eval_from
    while t < eval_to:
        recent_start = t - timedelta(days=recent_days - 1)
        # baseline stops right before recent starts - if it overlapped, a
        # spike would start dragging its own baseline up within days
        baseline_end = recent_start - timedelta(days=1)
        baseline_start = t - timedelta(days=baseline_days - 1)

        recent = _window_median(by_date, recent_start, t)
        baseline = _window_median(by_date, baseline_start, baseline_end)

        if recent is None or not baseline:
            # not enough history yet, or baseline is flat zero - no ratio to compare
            state = "normal"
        elif recent > spike_mult * baseline:
            state = "above"
        elif recent < reduced_mult * baseline:
            state = "below"
        else:
            state = "normal"

        frp_today = by_date[t].frp_sum if t in by_date else 0.0

        if episode is None:
            if state != "normal":
                episode = {
                    "direction": state,
                    "start_date": t,
                    "last_in_state_date": t,
                    "peak_frp": frp_today,
                    "baseline_frp": baseline,
                    "normal_streak": 0,
                }
        elif state == episode["direction"]:
            episode["last_in_state_date"] = t
            episode["normal_streak"] = 0
            # "peak" for a below-episode is the deepest dip, not max
            episode["peak_frp"] = (
                max(episode["peak_frp"], frp_today)
                if episode["direction"] == "above"
                else min(episode["peak_frp"], frp_today)
            )
        elif state == "normal":
            episode["normal_streak"] += 1
            if episode["normal_streak"] >= delay:
                finalize(end_date=episode["last_in_state_date"])
        else:
            # direct flip (above -> below or vice versa) with no normal gap
            finalize(end_date=episode["last_in_state_date"])
            episode = {
                "direction": state,
                "start_date": t,
                "last_in_state_date": t,
                "peak_frp": frp_today,
                "baseline_frp": baseline,
                "normal_streak": 0,
            }

        t += timedelta(days=1)

    if episode is not None:
        finalize(end_date=None)

    return events


# Everything below actually touches database: read facility_night per
# facility, run it through compute_events(), write results to flare_event


def run(p_from: date, p_to: date, detector_id: int | None = None) -> int:
    # Caller owns pool lifecycle (see app/cli.py) - already open here
    with pool.connection() as conn:
        if detector_id is None:
            row = conn.execute(
                "SELECT id, params FROM detector_version ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise RuntimeError("no detector_version row - run `bootstrap-detector` first")
            detector_id, params = row
        else:
            row = conn.execute(
                "SELECT params FROM detector_version WHERE id = %s", (detector_id,)
            ).fetchone()
            if row is None:
                raise RuntimeError(f"detector_version {detector_id} not found")
            (params,) = row

        history_from = p_from - timedelta(days=params["baseline_window_days"])
        facility_ids = [r[0] for r in conn.execute("SELECT id FROM facility").fetchall()]

        n_events = 0
        for facility_id in facility_ids:
            rows = conn.execute(
                """
                SELECT night_date, frp_sum, observable
                  FROM facility_night
                 WHERE facility_id = %s
                   AND night_date >= %s AND night_date < %s
                 ORDER BY night_date
                """,
                (facility_id, history_from, p_to),
            ).fetchall()
            nights = [
                NightRecord(night_date=r[0], frp_sum=r[1], observable=r[2]) for r in rows
            ]

            for ev in compute_events(nights, params, eval_from=p_from, eval_to=p_to):
                # upsert, not insert: an ongoing event (end_date NULL) just
                # gets its end_date/score updated the next time this runs
                conn.execute(
                    """
                    INSERT INTO flare_event
                        (facility_id, detector_id, kind, start_date, end_date,
                         peak_frp, baseline_frp, score, blind_nights)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (facility_id, detector_id, kind, start_date) DO UPDATE
                       SET end_date     = EXCLUDED.end_date,
                           peak_frp     = EXCLUDED.peak_frp,
                           baseline_frp = EXCLUDED.baseline_frp,
                           score        = EXCLUDED.score,
                           blind_nights = EXCLUDED.blind_nights
                    """,
                    (
                        facility_id,
                        detector_id,
                        ev.kind,
                        ev.start_date,
                        ev.end_date,
                        ev.peak_frp,
                        ev.baseline_frp,
                        ev.score,
                        ev.blind_nights,
                    ),
                )
                n_events += 1

        return n_events


if __name__ == "__main__":
    import sys

    pool.open()
    try:
        n = run(date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2]))
        print(f"inserted/updated {n} flare_event rows")
    finally:
        pool.close()
