from datetime import date, datetime, time, timedelta

# FIRMS reports acq_time/acq_date in UTC. night_date is the LOCAL calendar
# date the detection belongs to (see db/schema.sql). US VIIRS night overpasses
# cluster around 01:00-03:00 local and day overpasses around 12:00-14:00 local
# (checked against real FIRMS responses for Gulf Coast and Alaska regions) -
# comfortably clear of both the midnight and noon boundaries below, so a
# whole-hour longitude-based UTC offset (no DST, no per-point timezone lookup)
# is accurate enough for v0.1.
def parse_acq_time(acq_time: str) -> time:
    # FIRMS omits leading zeros, e.g. "638" for 06:38.
    hhmm = str(acq_time).zfill(4)
    return time(int(hhmm[:2]), int(hhmm[2:]))


def night_date(acq_date: date, acq_time: str, lon: float) -> date:
    acq_dt_utc = datetime.combine(acq_date, parse_acq_time(acq_time))
    offset_hours = round(lon / 15)
    local_dt = acq_dt_utc + timedelta(hours=offset_hours)

    # Local afternoon/evening (>=12:00) belongs to that calendar date's
    # night; local early morning (<12:00) is still part of the *previous*
    # evening's night - e.g. 02:00 UTC over Texas (UTC-6) is 20:00 local the
    # day before, i.e. that previous evening, not the UTC calendar date.
    if local_dt.hour >= 12:
        return local_dt.date()
    return local_dt.date() - timedelta(days=1)
