"""The dashboard dataset is what the site draws, so it is checked like a report.

Every club in the season in progress must have a history to be read against,
every interval must contain its point, and the Portuguese model must be the one
frozen in the pre-registration. A dataset that drifted from the live page would
put two different numbers for the same club on the same site.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"

#: Frozen in preregistrations/2026-08-30-porto-booking-index.md.
PORTO_INTERCEPT = 1.1259
PORTO_SLOPE = 0.095491


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads((DASHBOARD / "meta.json").read_text())


@pytest.fixture(scope="module")
def current() -> dict:
    return json.loads((DASHBOARD / "current.json").read_text())


def history(code: str) -> dict:
    return json.loads((DASHBOARD / "history" / f"{code}.json").read_text())


def test_no_nan_leaks_into_json() -> None:
    for path in DASHBOARD.rglob("*.json"):
        text = path.read_text()
        assert "NaN" not in text and "Infinity" not in text, path


def test_files_agree_on_snapshot(meta: dict, current: dict) -> None:
    latest = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1].name
    assert meta["snapshot"] == latest
    assert current["snapshot"] == latest
    for code in meta["leagues"]:
        assert history(code)["snapshot"] == latest, code


def test_portugal_model_is_the_frozen_one(meta: dict) -> None:
    model = meta["leagues"]["P1"]["model"]
    assert round(model["intercept"], 4) == PORTO_INTERCEPT
    assert round(model["slope"], 6) == PORTO_SLOPE


def test_every_current_club_has_a_league_history(meta: dict, current: dict) -> None:
    for code in current["leagues"]:
        assert code in meta["leagues"]
        past = history(code)["seasons"]
        assert past, code
        assert set(past) == set(meta["leagues"][code]["completed_seasons"])


def test_current_clubs_are_internally_consistent(current: dict) -> None:
    for code, league in current["leagues"].items():
        for name, club in league["clubs"].items():
            where = f"{code} {name}"
            assert club["lo"] <= club["index"] <= club["hi"], where
            assert club["shrunk_lo"] <= club["shrunk"] <= club["shrunk_hi"], where
            assert len(club["by_match"]) == club["matches"], where
            assert club["by_match"][-1]["cum_index"] == club["index"], where
            for key in ("league_percentile", "europe_percentile",
                        "league_history_percentile", "europe_history_percentile"):
                assert 0 <= club[key] <= 100, f"{where} {key}"
            assert club["survives_bh"] == (club["bh"] < 0.10), where
        assert sorted(league["survive_bh"]) == sorted(
            n for n, c in league["clubs"].items() if c["survives_bh"])


def test_completed_seasons_are_internally_consistent(meta: dict) -> None:
    for code in meta["leagues"]:
        for season, block in history(code)["seasons"].items():
            for name, club in block["clubs"].items():
                where = f"{code} {season} {name}"
                assert club["lo"] <= club["index"] <= club["hi"], where
                assert len(club["cum_index"]) == club["matches"], where
                assert math.isclose(club["cum_index"][-1], club["index"], abs_tol=1e-3), where


def test_quantiles_are_ordered(meta: dict, current: dict) -> None:
    def ordered(row: dict) -> bool:
        values = [row[k] for k in ("p05", "p25", "p50", "p75", "p95")]
        return all(a <= b for a, b in zip(values[:-1], values[1:], strict=True))

    assert all(ordered(r) for r in current["europe_cum_index_by_matchweek"].values())
    for code in meta["leagues"]:
        assert all(ordered(r) for r in history(code)["cum_index_by_matchweek"].values()), code
