from datetime import date, timedelta

from app.etl.event_detector import NightRecord, compute_events

# Small, hand-verifiable window sizes. recent_window_days=1 means "recent" is
# just that single night's own frp_sum (no smoothing), which keeps
# duration/delay/kind tests below arithmetic-free to trace by hand
PARAMS = {
    "spike_multiplier": 2.0,
    "reduced_multiplier": 0.5,
    "baseline_window_days": 21,
    "recent_window_days": 1,
    "event_min_duration_days": 4,
    "event_close_delay_nights": 2,
}

HIST_START = date(2020, 1, 1)
D = date(2020, 1, 25)  # comfortably past HIST_START + baseline_window_days
EVAL_FROM = date(2020, 1, 20)
EVAL_TO = date(2020, 2, 10)


def build_history(
    hist_start: date, hist_end: date, overrides: dict[date, tuple[float, bool | None]]
):
    """Flat baseline of frp_sum=10.0 with specific dates overridden"""
    nights = []
    d = hist_start
    while d <= hist_end:
        frp, observable = overrides.get(d, (10.0, None))
        nights.append(NightRecord(night_date=d, frp_sum=frp, observable=observable))
        d += timedelta(days=1)
    return nights


def test_short_burst_above_threshold_is_a_spike():
    overrides = {D: (40.0, None), D + timedelta(1): (40.0, None), D + timedelta(2): (40.0, None)}
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "spike"
    assert ev.start_date == D
    assert ev.end_date == D + timedelta(2)
    assert ev.peak_frp == 40.0
    assert ev.baseline_frp == 10.0
    assert ev.score == 4.0
    assert ev.blind_nights == 0


def test_sustained_burst_past_min_duration_is_regime_up():
    overrides = {D + timedelta(i): (40.0, None) for i in range(6)}  # D .. D+5, 6 nights
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "regime_up"
    assert ev.start_date == D
    assert ev.end_date == D + timedelta(5)
    assert ev.peak_frp == 40.0
    assert ev.score == 4.0


def test_sustained_drop_past_min_duration_is_regime_down():
    overrides = {D + timedelta(i): (2.0, None) for i in range(6)}  # ratio 2/10 = 0.2 < 0.5
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "regime_down"
    assert ev.start_date == D
    assert ev.end_date == D + timedelta(5)
    assert ev.peak_frp == 2.0  # the deepest point of the dip, not a max
    assert ev.score == 0.2


def test_single_normal_night_does_not_split_episode():
    # above, above, one dip back to normal (< delay=2), above, above, above
    overrides = {
        D: (40.0, None),
        D + timedelta(1): (40.0, None),
        D + timedelta(2): (10.0, None),  # single night dip, must not close event
        D + timedelta(3): (40.0, None),
        D + timedelta(4): (40.0, None),
        D + timedelta(5): (40.0, None),
    }
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    ev = events[0]
    assert ev.start_date == D
    assert ev.end_date == D + timedelta(5)
    assert ev.kind == "regime_up"
    assert ev.peak_frp == 40.0


def test_direct_flip_from_above_to_below_closes_and_opens_two_events():
    overrides = {
        D: (40.0, None),
        D + timedelta(1): (40.0, None),
        D + timedelta(2): (2.0, None),  # flips straight to "below", no normal gap
        D + timedelta(3): (2.0, None),
        D + timedelta(4): (2.0, None),
    }
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 2
    first, second = events
    assert first.kind == "spike"
    assert first.start_date == D
    assert first.end_date == D + timedelta(1)
    assert first.peak_frp == 40.0

    assert second.kind == "spike"
    assert second.start_date == D + timedelta(2)
    assert second.end_date == D + timedelta(4)
    assert second.peak_frp == 2.0


def test_episode_still_active_at_window_end_has_no_end_date():
    eval_to = date(2020, 2, 5)
    overrides = {}
    d = D
    while d < eval_to:
        overrides[d] = (40.0, None)
        d += timedelta(1)
    nights = build_history(HIST_START, eval_to, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, eval_to)

    assert len(events) == 1
    ev = events[0]
    assert ev.start_date == D
    assert ev.end_date is None
    assert ev.kind == "regime_up"


def test_blind_nights_counts_unobservable_nights_within_the_event_window():
    overrides = {
        D: (40.0, None),
        D + timedelta(1): (40.0, False),  # not observed that night
        D + timedelta(2): (40.0, None),
    }
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, PARAMS, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    assert events[0].blind_nights == 1


def test_insufficient_baseline_history_does_not_produce_a_false_event():
    # a single night with no prior history at all - baseline can't be computed
    lone_night = date(2020, 6, 1)
    nights = [NightRecord(night_date=lone_night, frp_sum=100.0, observable=None)]

    events = compute_events(nights, PARAMS, lone_night, lone_night + timedelta(1))

    assert events == []


def test_baseline_window_excludes_the_recent_window():
    # recent_window_days=3 here (unlike recent_window_days=1 used by every
    # other test in this file) so recent window actually spans multiple
    # nights. If baseline included those same nights, then spike would
    # drag its own baseline up to ~its own level within days and ratio
    # would collapse back toward 1, masking every spike it should flag
    params = {
        "spike_multiplier": 2.0,
        "reduced_multiplier": 0.5,
        "baseline_window_days": 30,
        "recent_window_days": 3,
        "event_min_duration_days": 4,
        "event_close_delay_nights": 2,
    }
    start = D
    overrides = {
        start: (40.0, None),
        start + timedelta(1): (40.0, None),
        start + timedelta(2): (40.0, None),
    }
    nights = build_history(HIST_START, EVAL_TO, overrides)

    events = compute_events(nights, params, EVAL_FROM, EVAL_TO)

    assert len(events) == 1
    assert events[0].kind == "spike"
    assert events[0].peak_frp == 40.0
    assert events[0].baseline_frp == 10.0
    assert events[0].score == 4.0
