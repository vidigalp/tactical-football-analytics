"""Recompute the dashboard from the raw snapshot and compare with what was published.

The dashboard is regenerated and pushed by a workflow with no person reading it.
This test is the reader. It rebuilds every count, expectation, interval, p-value,
percentile and pool from the parquet files using only the model constants the
dashboard itself publishes, with none of the helpers season_dashboard.py uses, so
a bug shared between the script and its own tests still shows up here.

Tolerances are set by the rounding in the files, not by taste: model constants are
printed to six places and multipliers to three, so an expectation recomputed from
them drifts by a few thousandths, and a percentile recomputed from indices rounded
to three places can move by one member of its pool when a tie appears or vanishes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads((DASHBOARD / "meta.json").read_text())


@pytest.fixture(scope="module")
def current() -> dict:
    return json.loads((DASHBOARD / "current.json").read_text())


@pytest.fixture(scope="module")
def history(meta: dict) -> dict[str, dict]:
    return {
        code: json.loads((DASHBOARD / "history" / f"{code}.json").read_text())
        for code in meta["leagues"]
    }


@pytest.fixture(scope="module")
def team_matches(meta: dict) -> pd.DataFrame:
    """One row per team per match, straight from the home and away columns."""
    snapshot = ROOT / "data" / "snapshots" / meta["snapshot"]
    raw = pd.concat(
        [pd.read_parquet(snapshot / e.parquet_path)
         for e in read_manifest(snapshot) if e.source == "football-data"],
        ignore_index=True,
    ).dropna(subset=["HF", "AF", "HY", "AY"])

    def side(home: bool) -> pd.DataFrame:
        p, q = ("H", "A") if home else ("A", "H")
        return pd.DataFrame({
            "Div": raw.Div, "season": raw.season, "Date": raw.Date,
            "team": raw[("Home" if home else "Away") + "Team"],
            "fouls": raw[p + "F"], "yellows": raw[p + "Y"], "reds": raw[p + "R"],
            "goals": raw["FT" + p + "G"], "goals_against": raw["FT" + q + "G"],
            "shots": raw[p + "S"], "shots_on_target": raw[p + "ST"], "corners": raw[p + "C"],
            "home": home,
        })

    return pd.concat([side(True), side(False)], ignore_index=True)


def poisson_interval(observed: int, expected: float) -> tuple[float, float]:
    low = stats.chi2.ppf(0.025, 2 * observed) / 2 if observed > 0 else 0.0
    return low / expected, stats.chi2.ppf(0.975, 2 * (observed + 1)) / 2 / expected


def two_sided(observed: int, expected: float) -> float:
    return min(1.0, 2 * min(stats.poisson.cdf(observed, expected),
                            1 - stats.poisson.cdf(observed - 1, expected)))


def benjamini_hochberg(p: dict[str, float]) -> dict[str, float]:
    series = pd.Series(p).sort_values()
    adjusted = (series * len(series) / np.arange(1, len(series) + 1))[::-1].cummin()[::-1]
    return adjusted.clip(upper=1.0).to_dict()


def assert_share_at_or_below(published: float, value: float, pool: list[float]) -> None:
    """The published share must sit between the strict and the inclusive share.

    Indices in the files are rounded to three places, so a value that was just
    above a pool member at full precision can tie with it after rounding. The
    truth lies between "strictly below" and "at or below", widened by the
    one-place rounding of the percentile itself.
    """
    arr = np.asarray(pool)
    below = 100 * float((arr < value - 0.0005).mean())
    at_or_below = 100 * float((arr <= value + 0.0005).mean())
    assert below - 0.06 <= published <= at_or_below + 0.06, (published, below, at_or_below)


def test_current_counts_match_the_raw_columns(meta: dict, current: dict,
                                              team_matches: pd.DataFrame) -> None:
    now = team_matches[team_matches.season == meta["current_season"]]
    now = now.assign(wins=now.goals > now.goals_against, draws=now.goals == now.goals_against,
                     losses=now.goals < now.goals_against)
    totals = now.groupby(["Div", "team"]).agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"),
        reds=("reds", "sum"), goals=("goals", "sum"), goals_against=("goals_against", "sum"),
        shots=("shots", "sum"), shots_on_target=("shots_on_target", "sum"),
        corners=("corners", "sum"), wins=("wins", "sum"), draws=("draws", "sum"),
        losses=("losses", "sum"), home_matches=("home", "sum"))
    for code, league in current["leagues"].items():
        assert set(league["clubs"]) == set(totals.loc[code].index), code
        assert list(league["clubs"]) == sorted(league["clubs"]), f"{code} not alphabetical"
        assert league["matches"] == int(totals.loc[code].matches.sum()) // 2, code
        assert league["yellows"] == int(totals.loc[code].yellows.sum()), code
        for team, club in league["clubs"].items():
            row = totals.loc[(code, team)]
            for field in totals.columns:
                assert club[field] == int(row[field]), (code, team, field)
            dates = [m["date"] for m in club["by_match"]]
            assert dates == sorted(dates), (code, team, "by_match order")
            assert sum(m["yellows"] for m in club["by_match"]) == club["yellows"], (code, team)
            assert sum(m["fouls"] for m in club["by_match"]) == club["fouls"], (code, team)


def test_current_statistics_follow_from_the_published_model(meta: dict, current: dict) -> None:
    every_index: list[float] = []
    for code, league in current["leagues"].items():
        model = meta["leagues"][code]["model"]
        multiplier = meta["leagues"][code]["situation_multiplier"]
        prior = meta["leagues"][code]["prior"]
        p_values: dict[str, float] = {}
        for team, club in league["clubs"].items():
            expected_era = 0.0
            expected = 0.0
            yellows = 0
            for match in club["by_match"]:
                era = model["intercept"] + model["slope"] * match["fouls"]
                scale = multiplier[match["band"]] if match["band"] else 1.0
                expected_era += era
                expected += era * scale
                yellows += match["yellows"]
                assert match["expected"] == pytest.approx(era * scale, abs=0.01), (code, team)
                assert match["cum_index"] == pytest.approx(yellows / expected, abs=0.004)
            assert club["expected_era"] == pytest.approx(expected_era, abs=0.03), (code, team)
            assert club["expected"] == pytest.approx(expected, abs=0.03), (code, team)
            assert club["index"] == pytest.approx(yellows / expected, abs=0.004), (code, team)
            lo, hi = poisson_interval(yellows, expected)
            assert club["lo"] == pytest.approx(lo, abs=0.004), (code, team)
            assert club["hi"] == pytest.approx(hi, abs=0.01), (code, team)
            assert club["p"] == pytest.approx(two_sided(yellows, expected), abs=0.004), (code, team)
            shrunk = (prior["shape"] + yellows) / (prior["rate"] + expected)
            assert club["shrunk"] == pytest.approx(shrunk, abs=0.004), (code, team)
            assert club["reliability"] == pytest.approx(
                expected / (prior["rate"] + expected), abs=0.004), (code, team)
            p_values[team] = club["p"]
            every_index.append(club["index"])
        adjusted = benjamini_hochberg(p_values)
        league_index = [c["index"] for c in league["clubs"].values()]
        for team, club in league["clubs"].items():
            assert club["bh"] == pytest.approx(adjusted[team], abs=0.004), (code, team)
            assert club["survives_bh"] == (club["bh"] < meta["fdr"]), (code, team)
            assert_share_at_or_below(club["league_percentile"], club["index"], league_index)
        assert league["survive_bh"] == sorted(
            t for t, c in league["clubs"].items() if c["survives_bh"]), code
    for league in current["leagues"].values():
        for club in league["clubs"].values():
            assert_share_at_or_below(club["europe_percentile"], club["index"], every_index)


def test_history_totals_match_the_raw_columns(meta: dict, history: dict[str, dict],
                                              team_matches: pd.DataFrame) -> None:
    done = team_matches[team_matches.season != meta["current_season"]]
    totals = done.groupby(["Div", "season", "team"]).agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"))
    for code, file in history.items():
        assert set(file["seasons"]) == set(meta["leagues"][code]["completed_seasons"]), code
        for season, block in file["seasons"].items():
            assert block["matches"] == sum(c["matches"] for c in block["clubs"].values()) // 2
            for team, club in block["clubs"].items():
                row = totals.loc[(code, season, team)]
                assert (club["matches"], club["fouls"], club["yellows"]) == (
                    int(row.matches), int(row.fouls), int(row.yellows)), (code, season, team)
                assert len(club["cum_index"]) == club["matches"], (code, season, team)
                assert club["cum_index"][-1] == pytest.approx(club["index"], abs=0.004)
                assert club["complete"] == (club["matches"] >= meta["complete_threshold"])
                lo, hi = poisson_interval(club["yellows"], club["expected"])
                assert club["lo"] == pytest.approx(lo, abs=0.004), (code, season, team)
                assert club["hi"] == pytest.approx(hi, abs=0.004), (code, season, team)


def test_bands_and_history_percentiles_are_the_completed_pool(
        meta: dict, current: dict, history: dict[str, dict]) -> None:
    europe: dict[int, list[float]] = {}
    league_pools: dict[str, dict[int, list[float]]] = {}
    for code, file in history.items():
        pool: dict[int, list[float]] = {}
        for block in file["seasons"].values():
            for club in block["clubs"].values():
                if club["complete"]:
                    for k, value in enumerate(club["cum_index"], 1):
                        pool.setdefault(k, []).append(value)
                        europe.setdefault(k, []).append(value)
        league_pools[code] = pool
        band = file["cum_index_by_matchweek"]
        assert set(band) == {str(k) for k in pool}, code
        for k, row in band.items():
            values = pool[int(k)]
            assert row["n"] == len(values), (code, k)
            for q, key in zip(meta["quantiles"], ["p05", "p25", "p50", "p75", "p95"], strict=True):
                assert row[key] == pytest.approx(np.quantile(values, q), abs=0.004), (code, k, key)
        assert file["band_summary"]["team_seasons"] == len(pool[1]), code
    assert len(europe[1]) == meta["team_seasons_completed"]
    for k, row in current["europe_cum_index_by_matchweek"].items():
        assert row["n"] == len(europe[int(k)]), k
        assert row["p50"] == pytest.approx(np.median(europe[int(k)]), abs=0.004), k
    for code, league in current["leagues"].items():
        for club in league["clubs"].values():
            k = club["matches"]
            assert_share_at_or_below(
                club["league_history_percentile"], club["index"], league_pools[code][k])
            assert_share_at_or_below(club["europe_history_percentile"], club["index"], europe[k])


def test_dashboard_agrees_with_the_live_page_sidecar(current: dict) -> None:
    sidecar = ROOT / "reports" / "live-season-portugal" / "season_status.json"
    status = json.loads(sidecar.read_text())
    if status["snapshot"] != current["snapshot"]:
        pytest.skip("live page is pinned to an older snapshot than the dashboard")
    clubs = current["leagues"]["P1"]["clubs"]
    for team, row in status["table"].items():
        for field in ("expected", "expected_era", "fouls", "yellows", "matches", "index",
                      "lo", "hi", "bh"):
            assert row[field] == clubs[team][field], (team, field)
    assert status["survive_bh"] == current["leagues"]["P1"]["survive_bh"]
