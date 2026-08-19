from datetime import date

from app.etl.night_date import night_date


def test_early_utc_morning_over_texas_is_the_previous_evening():
    # 02:00 UTC over Texas (UTC-6) is 20:00 local the day before
    # exact example from night_date comment in db/schema.sql.
    assert night_date(date(2021, 1, 2), "0200", -97.0) == date(2021, 1, 1)


def test_night_date_can_cross_a_year_boundary_backward():
    assert night_date(date(2021, 1, 1), "0200", -97.0) == date(2020, 12, 31)


def test_local_noon_belongs_to_that_calendar_date():
    assert night_date(date(2020, 6, 15), "1200", 0.0) == date(2020, 6, 15)


def test_just_before_local_noon_belongs_to_the_previous_date():
    assert night_date(date(2020, 6, 15), "1159", 0.0) == date(2020, 6, 14)


def test_local_midnight_belongs_to_the_previous_date():
    assert night_date(date(2020, 6, 15), "0000", 0.0) == date(2020, 6, 14)


def test_short_acq_time_without_leading_zero_is_parsed_correctly():
    # FIRMS CSV omits leading zeros, e.g. "638" for 06:38 UTC.
    assert night_date(date(2020, 6, 1), "638", 0.0) == date(2020, 5, 31)
