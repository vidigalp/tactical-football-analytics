"""Integrity of the committed match snapshot.

Runs against the data actually in the repo, so a bad ingest cannot be committed
unnoticed. Offline: reads the snapshot, never the network.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tfa.competitions import COMPETITIONS, season_start_year
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]

#: Upstream rows with shots on target exceeding total shots. These are errors in
#: the source data, not in our parsing. They affect shooting metrics only and are
#: excluded from any analysis that uses them; discipline work is unaffected.
#: Recorded rather than tolerated, so the count cannot grow unnoticed.
KNOWN_BAD_SHOT_ROWS = 3

#: One match (Turkey 2018-19, Bursaspor v Alanyaspor) has no away red-card value
#: upstream. Left as NA rather than filled with zero, which would invent a fact.
#: Only red-card analysis is affected, and it will drop the row.
KNOWN_MISSING_RED_CARDS = 1


@pytest.fixture(scope="module")
def matches() -> pd.DataFrame:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    if not entries:
        pytest.skip("no match snapshot committed")
    frame = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    frame["year"] = frame["season"].map(season_start_year)
    return frame


def test_all_leagues_present(matches):
    assert set(matches["Div"].unique()) == set(COMPETITIONS)


def test_no_duplicate_fixtures(matches):
    key = ["Div", "season", "Date", "HomeTeam", "AwayTeam"]
    assert matches.duplicated(subset=key).sum() == 0


def test_no_missing_dates(matches):
    assert matches["Date"].isna().sum() == 0


def test_discipline_columns_are_complete(matches):
    # Fouls and yellows are the reason these seasons were selected at all, and
    # the ingest filter guarantees them.
    for column in ("HF", "AF", "HY", "AY"):
        assert matches[column].notna().all(), column

    missing_reds = matches[["HR", "AR"]].isna().sum().sum()
    assert missing_reds == KNOWN_MISSING_RED_CARDS, (
        f"expected {KNOWN_MISSING_RED_CARDS} missing red-card value upstream, "
        f"found {missing_reds}"
    )


def test_counts_are_physically_plausible(matches):
    assert (matches[["HF", "AF"]].max() <= 50).all()
    assert (matches[["HY", "AY"]].max() <= 15).all()
    assert (matches[["HR", "AR"]].max() <= 5).all()
    assert (matches[["HF", "AF", "HY", "AY"]].min() >= 0).all()


def test_known_bad_shot_rows_have_not_grown(matches):
    bad = ((matches.HST > matches.HS) | (matches.AST > matches.AS)).sum()
    assert bad == KNOWN_BAD_SHOT_ROWS, (
        f"expected {KNOWN_BAD_SHOT_ROWS} upstream shot-count errors, found {bad}. "
        "If this grew, investigate before trusting any shooting metric."
    )


def test_team_counts_match_league_size(matches):
    """A stable team count per season means names are consistent across files.

    If a club were spelled two ways, this count would inflate and every
    team-level estimate would silently split in two.

    Restricted to completed seasons: in a season still in progress, a team that
    has not yet played at home is simply absent from the home-team column.
    """
    expected = {"E0": 20, "SP1": 20, "I1": 20, "D1": 18, "SC0": 12, "G1": 14}
    completed = matches[matches["year"] < matches["year"].max()]
    for code, size in expected.items():
        counts = (
            completed[completed.Div == code].groupby("season")["HomeTeam"].nunique()
        )
        assert counts.eq(size).all(), f"{code}: {counts[counts != size].to_dict()}"


def test_current_season_is_in_progress_not_broken(matches):
    """The newest season should be partial, and every team in it should be known.

    Guards the distinction between 'season under way' and 'ingest truncated':
    a partial season is expected, an unrecognised club name is not.
    """
    latest = matches["year"].max()
    current = matches[matches["year"] == latest]
    history = matches[matches["year"] < latest]

    for code, group in current.groupby("Div"):
        played = group.groupby("HomeTeam").size().sum()
        assert played > 0, code
        # Promoted clubs legitimately appear for the first time, so this only
        # asserts the season is not empty and names parse, not that all are seen.
        assert group["HomeTeam"].notna().all()
        assert group["AwayTeam"].notna().all()

    assert len(history) > len(current), "history must exceed the in-progress season"


def test_referee_present_only_where_expected(matches):
    coverage = matches.groupby("Div")["Referee"].apply(lambda s: s.notna().mean())
    assert coverage["E0"] > 0.99
    assert coverage["SC0"] > 0.90
    for code in ("SP1", "F1", "P1", "N1", "B1", "T1", "G1"):
        assert coverage[code] == 0, f"{code} unexpectedly has referee data"


def test_odds_coverage_is_near_complete(matches):
    # The strength control is only useful if it exists nearly everywhere.
    assert matches["strength_diff"].notna().mean() > 0.99


def test_devigged_probabilities_are_valid(matches):
    probs = matches[["p_home", "p_draw", "p_away"]].dropna()
    assert ((probs > 0) & (probs < 1)).all().all()
    total = probs.sum(axis=1)
    assert ((total - 1.0).abs() < 1e-9).all(), "de-vigged probabilities must sum to 1"


def test_overround_is_plausible(matches):
    """A retained price set must carry a real bookmaker margin.

    Rows implying an arbitrage are dropped at ingest, so any that survive here
    would mean that guard has regressed.
    """
    over = matches["odds_overround"].dropna()
    assert (over > 1.0).all(), "an overround at or below 1 is a bad price, not a market"
    assert over.median() < 1.15


def test_yellows_per_foul_uses_yellows_not_all_cards(matches):
    """The metric named for yellows must be computed from yellows.

    Regression test for a naming drift caught in review: the column was called
    'fouls_per_card' while the numerator was yellows alone. For teams with a red
    card the two differ, so the name was quietly wrong. Phatak et al. use yellow
    cards, so yellows is the correct numerator and the name now says so.
    """
    from tfa.metrics.discipline import team_season, with_shrinkage

    sample = matches[(matches.Div == "P1") & (matches.season == "2627")]
    if sample.empty:
        pytest.skip("no in-progress Portuguese season in this snapshot")

    teams = with_shrinkage(team_season(sample))
    reconstructed = teams["fouls"] / teams["yellows"]
    pd.testing.assert_series_equal(
        teams["fouls_per_yellow"].astype(float),
        reconstructed.astype(float),
        check_names=False,
    )
    # And it must NOT equal the version using yellows + reds, wherever reds exist.
    with_reds = teams["fouls"] / teams["cards"]
    assert (teams["fouls_per_yellow"] != with_reds).any(), (
        "if these never differ the test is not exercising the distinction"
    )
