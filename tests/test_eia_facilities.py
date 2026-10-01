import pandas as pd

from app.etl.eia_facilities import _registry_limitation_note, _registry_year


def test_registry_year_reads_eia_period_column() -> None:
    df = pd.DataFrame({"PERIOD": ["26", "26"]})

    assert _registry_year(df) == 2026


def test_registry_year_unknown_when_period_is_ambiguous() -> None:
    df = pd.DataFrame({"PERIOD": ["20", "26"]})

    assert _registry_year(df) is None


def test_registry_limitation_note_flags_mismatched_event_year() -> None:
    note = _registry_limitation_note(2026)

    assert "2026" in note
    assert "2020" in note
    assert "may be out of sync" in note
