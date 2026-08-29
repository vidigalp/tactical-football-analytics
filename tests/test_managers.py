"""Manager tenure dataset: the rules that stop a wrong attribution."""

from __future__ import annotations

import pandas as pd
import pytest

from tfa.managers import (
    COLUMNS,
    TenureError,
    attach,
    coverage,
    empty_frame,
    load,
    to_tenures,
    validate,
)


def make(rows: list[dict]) -> pd.DataFrame:
    frame = empty_frame()
    base = {
        "club": "Porto", "club_full": "FC Porto", "manager": "A Manager",
        "start_date": "2020-07-01", "start_precision": "day",
        "end_date": "2021-06-30", "end_precision": "day",
        "caretaker": "false", "source_url": "https://example.org/x",
        "confidence": "high", "notes": "",
    }
    return pd.concat(
        [frame, pd.DataFrame([{**base, **r} for r in rows])], ignore_index=True
    )


def test_empty_frame_has_all_columns():
    assert list(empty_frame().columns) == list(COLUMNS)


def test_valid_table_passes():
    validate(make([
        {"manager": "First", "start_date": "2019-07-01", "end_date": "2020-06-30"},
        {"manager": "Second", "start_date": "2020-07-01", "end_date": "2021-06-30"},
    ]))


def test_overlapping_tenures_are_rejected():
    """The important failure: one match credited to two managers."""
    with pytest.raises(TenureError, match="overlaps"):
        validate(make([
            {"manager": "First", "start_date": "2019-07-01", "end_date": "2020-12-31"},
            {"manager": "Second", "start_date": "2020-06-01", "end_date": "2021-06-30"},
        ]))


def test_ongoing_tenure_followed_by_another_is_rejected():
    with pytest.raises(TenureError, match="ongoing"):
        validate(make([
            {"manager": "First", "start_date": "2019-07-01", "end_date": ""},
            {"manager": "Second", "start_date": "2020-07-01", "end_date": ""},
        ]))


def test_row_without_a_source_is_rejected():
    with pytest.raises(TenureError, match="no source URL"):
        validate(make([{"source_url": ""}]))


def test_bad_precision_or_confidence_is_rejected():
    with pytest.raises(TenureError, match="start_precision"):
        validate(make([{"start_precision": "roughly"}]))
    with pytest.raises(TenureError, match="confidence"):
        validate(make([{"confidence": "probably"}]))


def test_month_precision_pins_to_first_of_month():
    tenures = to_tenures(make([
        {"start_date": "2020-09", "start_precision": "month", "end_date": ""}
    ]))
    assert tenures[0].start == pd.Timestamp("2020-09-01")


def test_two_clubs_may_hold_the_same_manager_at_different_times():
    validate(make([
        {"club": "Porto", "manager": "Same Person",
         "start_date": "2019-07-01", "end_date": "2020-06-30"},
        {"club": "Benfica", "manager": "Same Person",
         "start_date": "2020-07-01", "end_date": "2021-06-30"},
    ]))


def test_attach_labels_only_covered_matches():
    matches = pd.DataFrame({
        "Div": ["P1"] * 3,
        "season": ["1920"] * 3,
        "team": ["Porto"] * 3,
        "Date": pd.to_datetime(["2019-08-01", "2020-01-01", "2022-01-01"]),
    })
    tenures = make([
        {"manager": "In Post", "start_date": "2019-07-01", "end_date": "2020-06-30"}
    ])
    out = attach(matches, tenures)
    assert out["manager"].fillna("").tolist() == ["In Post", "In Post", ""]
    assert out["manager"].isna().sum() == 1
    # Match index counts appearances under that manager, for before/after work.
    covered = out[out["manager"].notna()]
    assert covered["manager_match_index"].tolist() == [1, 2]
    assert out["manager_match_index"].isna().sum() == 1


def test_coverage_is_reported_not_assumed():
    matches = pd.DataFrame({
        "Div": ["P1"] * 4,
        "season": ["1920"] * 4,
        "team": ["Porto"] * 4,
        "Date": pd.to_datetime(["2019-08-01", "2019-09-01", "2022-01-01", "2022-02-01"]),
    })
    tenures = make([
        {"manager": "In Post", "start_date": "2019-07-01", "end_date": "2020-06-30"}
    ])
    cov = coverage(matches, tenures)
    assert cov["coverage"].iloc[0] == 0.5


def test_committed_dataset_is_valid_if_present():
    """Whatever is committed must satisfy every rule above."""
    frame = load("primeira_liga")
    validate(frame)
