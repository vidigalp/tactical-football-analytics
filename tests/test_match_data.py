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
    """
    expected = {"E0": 20, "SP1": 20, "I1": 20, "D1": 18, "SC0": 12, "G1": 14}
    for code, size in expected.items():
        counts = (
            matches[matches.Div == code].groupby("season")["HomeTeam"].nunique()
        )
        assert counts.eq(size).all(), f"{code}: {counts[counts != size].to_dict()}"


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
