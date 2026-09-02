"""Where the current Primeira Liga season stands, from the newest snapshot.

Study 02 measured ten completed seasons. This reports the season in progress,
which is a different thing and is kept separate for that reason: four matches
cannot revise a ten-season estimate, and the pre-registered test in
preregistrations/ exists precisely so an early striking number does not get
treated as a conclusion.

This script reports. It does not resolve that test.

Run: uv run python scripts/season_status.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.viz import season as season_viz
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]
REPORT = "live-season-portugal"
SEASON = "2627"

#: Pre-match role from the devigged odds, as study 02 defines it.
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]

#: Frozen in the pre-registration on 2026-08-30 and not refitted here.
#: The false-discovery rate the screen is capped at, per METHODS.md section 5.
FDR = 0.10

AFFINE_INTERCEPT = 1.1259
AFFINE_SLOPE = 0.095491


def team_rows(matches: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame({
        "date": matches.Date, "team": matches.HomeTeam, "opponent": matches.AwayTeam,
        "fouls": matches.HF, "yellows": matches.HY, "strength": matches.strength_diff,
    })
    away = pd.DataFrame({
        "date": matches.Date, "team": matches.AwayTeam, "opponent": matches.HomeTeam,
        "fouls": matches.AF, "yellows": matches.AY, "strength": -matches.strength_diff,
    })
    return pd.concat([home, away], ignore_index=True)


def interval(observed: float, expected: float) -> tuple[float, float]:
    low = stats.chi2.ppf(0.025, 2 * observed) / 2 if observed > 0 else 0.0
    high = stats.chi2.ppf(0.975, 2 * (observed + 1)) / 2
    return low / expected, high / expected


def main() -> None:
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    frame = pd.read_parquet(next(snapshot.glob("football-data__P1__*.parquet")))
    frame = frame.dropna(subset=["HF", "AF", "HY", "AY"])

    history = team_rows(frame[frame.season != SEASON].dropna(subset=["strength_diff"]))
    current = team_rows(frame[frame.season == SEASON].dropna(subset=["strength_diff"]))

    # The situation multiplier comes from completed seasons only. Estimating it
    # on four matchweeks would let the thing being measured set its own baseline.
    history["expected"] = AFFINE_INTERCEPT + AFFINE_SLOPE * history.fouls
    history["band"] = pd.cut(history.strength, BANDS, labels=NAMES)
    multiplier = history.groupby("band", observed=True).apply(
        lambda g: g.yellows.sum() / g.expected.sum(), include_groups=False)

    current = current.copy()
    current["expected"] = AFFINE_INTERCEPT + AFFINE_SLOPE * current.fouls
    current["band"] = pd.cut(current.strength, BANDS, labels=NAMES)
    current["expected_adj"] = current.expected * current.band.map(
        multiplier).astype(float).fillna(1.0)

    clubs = current.groupby("team").agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"),
        e_era=("expected", "sum"), e_situation=("expected_adj", "sum"))
    clubs["index_era"] = clubs.yellows / clubs.e_era
    clubs["index_situation"] = clubs.yellows / clubs.e_situation
    clubs["p"] = [
        2 * min(stats.poisson.cdf(y, e), 1 - stats.poisson.cdf(y - 1, e))
        for y, e in zip(clubs.yellows, clubs.e_situation, strict=True)
    ]

    # The same screen against the era-only expectation, so the difference the
    # situation adjustment makes is a reported number rather than an assertion.
    # It is the entire subject of study 02's Wrong (1), and it was quoted in
    # prose without any script computing it.
    clubs["p_era"] = [
        2 * min(stats.poisson.cdf(y, e), 1 - stats.poisson.cdf(y - 1, e))
        for y, e in zip(clubs.yellows, clubs.e_era, strict=True)
    ]

    # Benjamini-Hochberg across every club in the league. Reporting the extreme
    # one of eighteen without this is how a finding gets manufactured.
    def benjamini_hochberg(column: str) -> pd.Series:
        ranked = clubs.sort_values(column).reset_index()
        count = len(ranked)
        adjusted = (
            (ranked[column] * count / (ranked.index + 1))[::-1].cummin()[::-1]
        ).clip(upper=1)
        return pd.Series(adjusted.to_numpy(), index=ranked["team"])

    clubs["bh"] = benjamini_hochberg("p")
    clubs["bh_era"] = benjamini_hochberg("p_era")
    count = len(clubs)
    clubs["survives_bh"] = clubs.bh < FDR

    print(f"snapshot {snapshot.name}   season {SEASON}   "
          f"{len(current) // 2} matches to {str(current.date.max())[:10]}")
    print("situation multiplier from completed seasons:")
    print("  " + "  ".join(f"{k}={v:.3f}" for k, v in multiplier.items()))
    print()
    ordered = clubs.sort_values("index_situation")
    print(ordered[["matches", "fouls", "yellows", "e_situation", "index_situation",
                   "p", "bh", "survives_bh"]].to_string(
        float_format=lambda v: f"{v:.3f}"))
    survivors = ordered[ordered.survives_bh]
    print(f"\nsurvive BH at {FDR}: {len(survivors)} of {count}"
          f"   naive p < 0.05: {int((clubs.p < 0.05).sum())}")

    facts = {
        "snapshot": snapshot.name,
        "season": SEASON,
        "matches": int(len(current) // 2),
        "latest_date": str(current.date.max())[:10],
        "clubs": int(count),
        "survive_bh": [str(t) for t in survivors.index],
        "bh_fdr": FDR,
        "naive_significant": int((clubs.p < 0.05).sum()),
        "situation_multiplier": {str(k): round(float(v), 3) for k, v in multiplier.items()},
        "table": {
            str(team): {
                "matches": int(row.matches),
                "fouls": int(row.fouls),
                "yellows": int(row.yellows),
                # Both steps, because the report contrasts them: the era-only
                # expectation is what the situation adjustment then moves.
                "expected_era": round(float(row.e_era), 2),
                "expected": round(float(row.e_situation), 2),
                "index": round(float(row.index_situation), 3),
                "lo": round(interval(row.yellows, row.e_situation)[0], 3),
                "hi": round(interval(row.yellows, row.e_situation)[1], 3),
                "bh": round(float(row.bh), 4),
                "bh_era": round(float(row.bh_era), 4),
            }
            for team, row in ordered.iterrows()
        },
    }
    # Interval columns for the figure. The JSON computes these inline per row;
    # the chart needs them as columns, and computing them twice would be two
    # places for the same number to drift.
    bounds = [interval(y, e) for y, e in zip(clubs.yellows, clubs.e_situation, strict=True)]
    clubs["lo"] = [b[0] for b in bounds]
    clubs["hi"] = [b[1] for b in bounds]
    clubs["booking_index"] = clubs.index_situation

    theme.apply()
    for path in season_viz.league_caterpillar(
        clubs, ROOT / "reports" / REPORT / "figures" / "fig1-league-so-far",
        highlight="Porto", season_label=f"20{SEASON[:2]}-{SEASON[2:]}",
        matches=len(current) // 2, snapshot=snapshot.name,
    ):
        print(f"wrote {path.relative_to(ROOT)}")

    out = ROOT / "reports" / REPORT / "season_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
