"""Guards on the competition registry.

These encode facts verified empirically against live files on 2026-08-29. If one
of them fails, the world changed and a finding needs revisiting — that is the
point of asserting them.
"""

from __future__ import annotations

import pytest

from tfa.competitions import (
    COMPETITIONS,
    CORE_COLUMNS,
    DEPRECATED_COLUMNS,
    FIRST_STATS_SEASON_YEAR,
    REFEREE_LEAGUES,
    SECOND_YELLOW_FOLDED_INTO_RED,
    UNDERSTAT_LEAGUES,
    available_seasons,
    season_code,
    season_start_year,
    seasons_range,
    usable_seasons,
)


def test_eleven_competitions():
    assert len(COMPETITIONS) == 11


def test_referee_available_only_in_england_and_scotland():
    # Verified by header audit across all 11 divisions, seasons 2425 and 2526.
    # An earlier assumption that referee was broadly available was wrong.
    assert set(REFEREE_LEAGUES) == {"E0", "SC0"}


def test_second_yellow_convention_matches_referee_leagues():
    # Both quirks happen to apply to the same two associations; assert it
    # explicitly so a future edit to one does not silently desync the other.
    assert sorted(SECOND_YELLOW_FOLDED_INTO_RED) == ["E0", "SC0"]


def test_understat_is_big_five_only():
    assert set(UNDERSTAT_LEAGUES) == {"E0", "D1", "I1", "SP1", "F1"}
    assert all(code in COMPETITIONS for code in UNDERSTAT_LEAGUES)


def test_portugal_gap_is_recorded():
    portugal = COMPETITIONS["P1"]
    assert portugal.season_gaps == ("9798", "9899", "9900")


def test_available_seasons_excludes_known_gaps():
    seasons = available_seasons("P1", 1996, 2001)
    assert "9798" not in seasons
    assert "9899" not in seasons
    assert "9900" not in seasons
    assert "9697" in seasons
    assert "0001" in seasons


def test_available_seasons_keeps_gaps_for_other_leagues():
    # The Portugal gap must not leak into other competitions.
    assert "9798" in available_seasons("E0", 1996, 2001)


@pytest.mark.parametrize(
    ("start", "expected"),
    [(2025, "2526"), (1999, "9900"), (2009, "0910"), (1993, "9394")],
)
def test_season_code(start, expected):
    assert season_code(start) == expected


def test_seasons_range_is_inclusive():
    assert seasons_range(2023, 2025) == ["2324", "2425", "2526"]


def test_url_construction():
    assert COMPETITIONS["P1"].url("2526") == (
        "https://www.football-data.co.uk/mmz4281/2526/P1.csv"
    )


def test_season_start_year_roundtrips():
    for year in range(1993, 2026):
        assert season_start_year(season_code(year)) == year


def test_season_codes_must_not_be_sorted_as_strings():
    # The bug this guards: "0001" (2000-01) sorts before "9394" (1993-94).
    codes = ["9394", "0001", "2526"]
    assert sorted(codes) == ["0001", "2526", "9394"]  # wrong chronologically
    assert sorted(codes, key=season_start_year) == ["9394", "0001", "2526"]


def test_scotland_referee_gap_recorded():
    assert COMPETITIONS["SC0"].referee_gaps == ("1213",)


def test_deprecated_columns_are_disjoint_from_core():
    assert not set(DEPRECATED_COLUMNS) & set(CORE_COLUMNS)


def test_first_stats_season_is_2000():
    # Files before 2000-01 carry results and odds only.
    assert FIRST_STATS_SEASON_YEAR == 2000


def test_discipline_windows_match_audit():
    # Verified 2026-08-29: match stats arrived league by league, never backfilled.
    expected = {
        "E0": 2000, "SC0": 2000, "D1": 2000, "I1": 2005, "SP1": 2005,
        "F1": 2007, "N1": 2017, "P1": 2017, "T1": 2017, "B1": 2019, "G1": 2019,
    }
    assert {c: k.discipline_from for c, k in COMPETITIONS.items()} == expected


def test_usable_seasons_is_shorter_than_available():
    # The gap between "a file exists" and "the file has fouls in it".
    assert len(usable_seasons("P1", 2025)) == 9
    assert len(available_seasons("P1", 2000, 2025)) == 26


def test_total_usable_league_seasons():
    total = sum(len(usable_seasons(c, 2025)) for c in COMPETITIONS)
    assert total == 179


def test_germany_discipline_series_is_interrupted():
    # Germany is the only league whose fouls/cards series has a hole in it.
    assert COMPETITIONS["D1"].discipline_gaps == ("0203",)
    assert "0203" not in usable_seasons("D1", 2025)
    assert "0102" in usable_seasons("D1", 2025)
    assert "0304" in usable_seasons("D1", 2025)


def test_full_core_never_precedes_discipline():
    for comp in COMPETITIONS.values():
        assert comp.full_core_from >= comp.discipline_from
