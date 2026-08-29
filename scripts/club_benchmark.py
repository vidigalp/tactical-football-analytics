"""Benchmark clubs against their league, and against each other.

Reports a booking index — yellows received divided by yellows expected at the
league's own rate for that many fouls, that season — which removes the era trend
in refereeing strictness.

It does NOT remove match context, and that matters here. Stronger clubs face
weaker opponents, lead more often, and commit more of their fouls far from their
own goal. Any of those could depress the booking index without a club doing
anything distinctive. So the pre-match strength gap implied by the betting odds
is reported alongside, and a like-for-like comparison restricted to matches of
similar strength is run underneath.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import season_start_year
from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 240)
BIG = ["Porto", "Benfica", "Sp Lisbon", "Sp Braga"]
LABEL = {"Porto": "Porto", "Benfica": "Benfica",
         "Sp Lisbon": "Sporting CP", "Sp Braga": "Braga"}


def poisson_ratio_ci(observed: float, expected: float) -> tuple[float, float]:
    lo = stats.chi2.ppf(0.025, 2 * observed) / 2 if observed > 0 else 0.0
    hi = stats.chi2.ppf(0.975, 2 * (observed + 1)) / 2
    return lo / expected, hi / expected


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [
        e for e in read_manifest(directory)
        if e.source == "football-data" and e.competition == "P1"
    ]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    tm = to_team_match(matches)
    tm["yr"] = tm["season"].map(season_start_year)

    lg = tm.groupby("season", as_index=False).agg(
        lg_fouls=("fouls", "sum"), lg_yellows=("yellows", "sum"),
        lg_n=("fouls", "size"),
    )
    lg["lg_ypf"] = lg.lg_yellows / lg.lg_fouls
    lg["lg_fouls_pm"] = lg.lg_fouls / lg.lg_n
    tm = tm.merge(lg[["season", "lg_ypf", "lg_fouls_pm"]], on="season")
    tm["exp_yellows"] = tm["fouls"] * tm["lg_ypf"]

    print(f"=== Primeira Liga {tm.yr.min()}-{tm.yr.max()}: "
          f"{len(tm):,} team-matches, {tm.team.nunique()} clubs ===")
    print(f"league: {tm.fouls.mean():.2f} fouls/match, {tm.yellows.mean():.2f} "
          f"yellows/match, {tm.fouls.sum()/tm.yellows.sum():.2f} fouls per yellow\n")

    club = tm.groupby("team", as_index=False).agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"),
        yellows=("yellows", "sum"), exp=("exp_yellows", "sum"),
        strength=("strength_diff", "mean"),
    )
    club = club[club.matches >= 100]
    club["fouls_pm"] = club.fouls / club.matches
    club["fouls_per_yellow"] = club.fouls / club.yellows
    club["booking_index"] = club.yellows / club.exp
    ci = [poisson_ratio_ci(y, e) for y, e in zip(club.yellows, club.exp, strict=True)]
    club["lo"], club["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    club["separates"] = (club.lo > 1.0) | (club.hi < 1.0)
    club = club.sort_values("booking_index")

    print("=== Every club with 100+ matches, by booking index ===")
    print("(strength = mean odds-implied log-odds of winning; higher is a stronger side)")
    view = club[["team", "matches", "fouls_pm", "fouls_per_yellow",
                 "booking_index", "lo", "hi", "separates", "strength"]]
    print(view.round(3).to_string(index=False))

    print("\n=== The big four ===")
    big = club[club.team.isin(BIG)].copy()
    big["club"] = big.team.map(LABEL)
    print(big[["club", "matches", "fouls_pm", "fouls_per_yellow",
               "booking_index", "lo", "hi", "strength"]].round(3).to_string(index=False))

    # Like-for-like: restrict everyone to matches where they were similarly
    # favoured, so the comparison is not driven by fixture difficulty.
    print("\n=== Like-for-like: matches where the club was a strong favourite ===")
    print("(odds-implied log-odds of winning above 1.0 — roughly 2.7:1 or better)")
    fav = tm[tm.strength_diff > 1.0]
    lf = fav.groupby("team", as_index=False).agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"),
        yellows=("yellows", "sum"), exp=("exp_yellows", "sum"),
    )
    lf = lf[lf.matches >= 50]
    lf["booking_index"] = lf.yellows / lf.exp
    ci = [poisson_ratio_ci(y, e) for y, e in zip(lf.yellows, lf.exp, strict=True)]
    lf["lo"], lf["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    lf["club"] = lf.team.map(lambda t: LABEL.get(t, t))
    print(f"league booking index among these matches: "
          f"{fav.yellows.sum() / fav.exp_yellows.sum():.3f}")
    print(lf.sort_values("booking_index")[
        ["club", "matches", "booking_index", "lo", "hi"]].round(3).to_string(index=False))

    print("\n=== Big four, season by season (booking index) ===")
    per = tm[tm.team.isin(BIG)].groupby(["yr", "team"]).apply(
        lambda g: g.yellows.sum() / g.exp_yellows.sum(), include_groups=False
    ).unstack()
    per.columns = [LABEL[c] for c in per.columns]
    print(per.round(2).to_string())

    print("\n=== Are the big four different from each other? ===")
    pairs = [(a, b) for i, a in enumerate(BIG) for b in BIG[i + 1:]]
    for a, b in pairs:
        ra, rb = club[club.team == a].iloc[0], club[club.team == b].iloc[0]
        # Poisson rate-ratio test on observed vs expected yellows.
        table = [[ra.yellows, ra.exp], [rb.yellows, rb.exp]]
        ratio = (table[0][0] / table[0][1]) / (table[1][0] / table[1][1])
        se = np.sqrt(1 / ra.yellows + 1 / rb.yellows)
        z = np.log(ratio) / se
        p = 2 * (1 - stats.norm.cdf(abs(z)))
        flag = "differ" if p < 0.05 else "indistinguishable"
        print(f"  {LABEL[a]:12s} vs {LABEL[b]:12s}  ratio {ratio:.3f}  p={p:.3f}  {flag}")


if __name__ == "__main__":
    main()
