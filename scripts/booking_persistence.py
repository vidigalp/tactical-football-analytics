"""Does a club's booking index carry over to the next season?

Written because study 03 cited this result and attributed it to study 02, which
did not contain it: the number had been computed once and never committed. That
is the same failure that put a wrong-signed correlation into study 02, so the fix
is a script rather than a sentence.

Run: uv run python scripts/booking_persistence.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import is_completed, season_start_year

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"

#: Below this a club-season is too short to carry a rate at all.
MIN_MATCHES = 25

#: Degree of the polynomial in pre-match strength used to absorb the situation
#: effect. Study 02 established that a coarse banding under-corrects the
#: strongest clubs, so the adjustment is continuous.
STRENGTH_DEGREE = 4


def load(snapshot: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(snapshot.glob("football-data__*.parquet")):
        frame = pd.read_parquet(path)
        if "strength_diff" not in frame:
            continue
        frame = frame.dropna(subset=["HF", "AF", "HY", "AY", "strength_diff"])
        frames.append(frame.assign(lg=path.name.split("__")[1]))
    matches = pd.concat(frames, ignore_index=True)
    matches["yr"] = matches["season"].map(season_start_year)
    # Retrospective: the season in progress is excluded. See
    # competitions.LAST_COMPLETED_SEASON_YEAR for why this matters more than
    # tidiness — the live season is the one under investigation.
    return matches[matches["season"].map(is_completed)]


def team_rows(matches: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame({"lg": matches.lg, "yr": matches.yr, "team": matches.HomeTeam,
                         "f": matches.HF, "y": matches.HY, "s": matches.strength_diff})
    away = pd.DataFrame({"lg": matches.lg, "yr": matches.yr, "team": matches.AwayTeam,
                         "f": matches.AF, "y": matches.AY, "s": -matches.strength_diff})
    return pd.concat([home, away], ignore_index=True)


def expectation(teams: pd.DataFrame) -> pd.DataFrame:
    """Cards expected from a team's fouls, after era and match situation.

    Fitted per league so nothing is pooled across them, which Phatak et al.
    (2021) show inverts trends on this ratio.
    """
    out = []
    for _, group in teams.groupby("lg"):
        group = group.copy()
        era = group.groupby("yr").apply(
            lambda g: g.y.sum() / g.f.sum(), include_groups=False).rename("rate")
        group = group.merge(era, left_on="yr", right_index=True)
        offset = np.log(np.maximum((group.f * group.rate).to_numpy(float), 1e-9))

        strength = group.s.to_numpy(float)
        design = np.column_stack([strength ** k for k in range(STRENGTH_DEGREE + 1)])
        cards = group.y.to_numpy(float)
        beta = np.zeros(design.shape[1])
        for _ in range(80):
            mu = np.exp(np.clip(design @ beta + offset, -20, 20))
            weighted = design.T * mu
            working = design @ beta + (cards - mu) / np.maximum(mu, 1e-9)
            step = np.linalg.solve(
                weighted @ design + 1e-9 * np.eye(design.shape[1]), weighted @ working)
            if np.max(np.abs(step - beta)) < 1e-10:
                beta = step
                break
            beta = step
        group["expected"] = np.exp(np.clip(design @ beta + offset, -20, 20))
        out.append(group)
    return pd.concat(out, ignore_index=True)


def main() -> None:
    # Latest snapshot, so this moves forward with the data rather than being
    # frozen. One consequence is worth stating, because it looks like a bug:
    # MIN_MATCHES keeps the in-progress season out of the *pairs*, but the era
    # rate and the strength polynomial are still fitted on every row, the
    # current season included. So each matchweek nudges the nuisance fit, and
    # with it every historical index. The movement is in the fourth decimal —
    # r ran 0.32429 to 0.32442 across one matchweek — and no published numeral
    # changes at the precision it is quoted to. A future reader who diffs this
    # sidecar and finds it moved has not found an error.
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    teams = expectation(team_rows(load(snapshot)))

    seasons = teams.groupby(["lg", "team", "yr"], as_index=False).agg(
        n=("f", "size"), y=("y", "sum"), expected=("expected", "sum"))
    seasons = seasons[seasons.n >= MIN_MATCHES].copy()
    seasons["index"] = seasons.y / seasons.expected

    seasons = seasons.sort_values(["lg", "team", "yr"])
    seasons["previous"] = seasons.groupby(["lg", "team"])["index"].shift(1)
    seasons["previous_yr"] = seasons.groupby(["lg", "team"])["yr"].shift(1)
    pairs = seasons[seasons.previous.notna() & (seasons.yr - seasons.previous_yr == 1)]

    r, p = stats.pearsonr(pairs.previous, pairs["index"])

    # How much of the spread between clubs is a real club property rather than
    # the Poisson noise of a season's worth of cards?
    observed = float(seasons["index"].var(ddof=1))
    sampling = float((seasons.y / seasons.expected ** 2).mean())
    true = max(observed - sampling, 0.0)

    per_league = []
    for lg, group in pairs.groupby("lg"):
        rr, pp = stats.pearsonr(group.previous, group["index"])
        per_league.append({"lg": lg, "pairs": len(group), "r": rr, "p": pp})

    facts = {
        "pairs": int(len(pairs)),
        "leagues": int(pairs.lg.nunique()),
        "r": r,
        "p": p,
        "r_squared": r * r,
        "variance_observed": observed,
        "variance_sampling": sampling,
        "variance_true": true,
        "true_share": true / observed,
        "true_sd": float(np.sqrt(true)),
        "positive_leagues": int(sum(1 for x in per_league if x["r"] > 0)),
        "per_league": per_league,
    }
    (ROOT / "reports" / REPORT / "persistence.json").write_text(
        json.dumps(facts, indent=2, sort_keys=True) + "\n")

    print(f"{len(pairs):,} consecutive club-season pairs, {pairs.lg.nunique()} leagues")
    print(f"  r = {r:+.3f}  p = {p:.2e}   positive in "
          f"{facts['positive_leagues']}/{pairs.lg.nunique()} leagues")
    print(f"  true between-club share of variance: {facts['true_share']:.0%}"
          f"   true SD {facts['true_sd']:.3f}")
    for row in sorted(per_league, key=lambda x: x["lg"]):
        print(f"    {row['lg']:<4} pairs={row['pairs']:>4}  r={row['r']:+.3f}")


if __name__ == "__main__":
    main()
