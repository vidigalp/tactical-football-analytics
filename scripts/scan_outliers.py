"""Cross-league outlier scan for the current season.

Asks two questions that a leaderboard cannot:

1. Against its own league's prior, is any team's discipline rate separable from
   its league mean at all?
2. How often does a run this extreme occur by chance? Twenty-six years of
   history gives an empirical answer rather than an assumed distribution.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import season_start_year
from tfa.metrics.discipline import team_season
from tfa.snapshot import read_manifest
from tfa.stats.shrinkage import beta_binomial_prior, shrink_beta_binomial

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 220)


def load(directory: Path) -> pd.DataFrame:
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    frame = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    frame["year"] = frame["season"].map(season_start_year)
    return frame


def scan_current(teams: pd.DataFrame) -> pd.DataFrame:
    """Shrink within each league, then score against that league's own mean."""
    out = []
    for (div, _season), g in teams.groupby(["Div", "season"], sort=False):
        g = g.reset_index(drop=True)
        prior = beta_binomial_prior(g["yellows"], g["fouls"])
        est = shrink_beta_binomial(g["yellows"], g["fouls"], prior)

        post_a = prior.alpha + g["yellows"].to_numpy(float)
        post_b = prior.beta + (g["fouls"].to_numpy(float) - g["yellows"].to_numpy(float))

        # Posterior probability the team's booking rate per foul is BELOW its
        # league mean — i.e. that it is genuinely more lenient, not just lucky.
        g["p_below_league"] = stats.beta.cdf(prior.mean, post_a, post_b)
        g["league_mean_rate"] = prior.mean
        g["league_fouls_per_yellow"] = 1.0 / prior.mean
        g["shrunk_rate"] = est["shrunk"]
        g["fouls_per_yellow"] = np.where(
            g["yellows"] > 0, g["fouls"] / g["yellows"].replace(0, np.nan), np.inf
        )
        g["fouls_per_yellow_shrunk"] = 1.0 / est["shrunk"]
        g["fpy_lo"] = 1.0 / est["upper"]
        g["fpy_hi"] = 1.0 / est["lower"]
        g["detectable"] = prior.detectable_variance
        g["league"] = div
        out.append(g)
    return pd.concat(out, ignore_index=True)


def historical_baseline(matches: pd.DataFrame, fouls: int, yellows: int,
                        window: int) -> dict[str, float]:
    """How often has any team, in any league, opened this leniently?

    Counts every team-season's first *window* matches across the whole archive
    and asks how many were at least as extreme: at least this many fouls while
    conceding no more than this many yellows.
    """
    from tfa.ingest.matches import to_team_match

    tm = to_team_match(matches)
    tm = tm.sort_values(["Div", "season", "team", "Date"])
    opening = tm.groupby(["Div", "season", "team"]).head(window)

    agg = opening.groupby(["Div", "season", "team"]).agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum")
    )
    agg = agg[agg["matches"] == window]

    at_least_as_extreme = agg[(agg["fouls"] >= fouls) & (agg["yellows"] <= yellows)]
    # A looser comparison on the ratio alone, for teams that fouled less.
    ratio = fouls / max(yellows, 1)
    by_ratio = agg[(agg["yellows"] > 0) & (agg["fouls"] / agg["yellows"] >= ratio)]
    zero = agg[agg["yellows"] == 0]

    return {
        "team_season_openings": len(agg),
        "as_extreme_both": len(at_least_as_extreme),
        "as_extreme_ratio": len(by_ratio) + len(zero),
        "zero_yellow_openings": len(zero),
        "pct_both": 100.0 * len(at_least_as_extreme) / len(agg),
        "pct_ratio": 100.0 * (len(by_ratio) + len(zero)) / len(agg),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2627")
    parser.add_argument("--team", default="Porto")
    args = parser.parse_args()

    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    matches = load(directory)

    current = matches[matches["season"] == args.season]
    teams = scan_current(team_season(current))

    print(f"=== CURRENT SEASON {args.season} — all leagues ===")
    print(f"{len(teams)} teams across {teams['league'].nunique()} leagues, "
          f"latest match {current['Date'].max().date()}\n")

    view = teams.sort_values("fouls_per_yellow", ascending=False)
    cols = ["league", "team", "matches", "fouls", "yellows", "fouls_per_yellow",
            "fouls_per_yellow_shrunk", "fpy_lo", "fpy_hi",
            "league_fouls_per_yellow", "p_below_league"]
    print("TOP 12 BY RAW RATIO")
    print(view[cols].head(12).round(2).to_string(index=False))

    print("\n=== Does ANY team separate from its own league mean? ===")
    n = len(teams)
    strong = teams[teams["p_below_league"] > 0.95]
    watch = teams[(teams["p_below_league"] > 0.90) & (teams["p_below_league"] <= 0.95)]
    print(f"teams scanned                       : {n}")
    print(f"P(rate below league mean) > 0.95    : {len(strong)}")
    print(f"                    0.90 to 0.95    : {len(watch)}")
    print(f"leagues where teams are separable   : "
          f"{teams.groupby('league')['detectable'].first().sum()} of "
          f"{teams['league'].nunique()}")
    if len(strong):
        print(strong[cols].round(2).to_string(index=False))
    expected_by_chance = 0.05 * n
    print(f"\nby chance alone, scanning {n} teams at a 0.05 tail you would expect "
          f"~{expected_by_chance:.0f} teams above 0.95")
    if len(strong) < expected_by_chance:
        print("  -> FEWER flagged than chance predicts. No evidence of a real "
              "outlier anywhere in Europe this week.")

    target = teams[teams["team"] == args.team]
    if not target.empty:
        t = target.iloc[0]
        print(f"\n=== {args.team} ===")
        print(f"  {int(t.matches)} matches, {int(t.fouls)} fouls, {int(t.yellows)} yellows")
        print(f"  raw            : {t.fouls_per_yellow:.1f} fouls per yellow")
        print(f"  shrunk         : {t.fouls_per_yellow_shrunk:.1f} "
              f"[{t.fpy_lo:.1f}, {t.fpy_hi:.1f}]")
        print(f"  league mean    : {t.league_fouls_per_yellow:.1f}")
        print(f"  P(below league): {t.p_below_league:.3f}")
        print(f"  league interval overlaps league mean: "
              f"{t.fpy_lo <= t.league_fouls_per_yellow <= t.fpy_hi}")

        print("\n=== HISTORICAL BASELINE (all leagues, all seasons since 2000) ===")
        base = historical_baseline(matches, int(t.fouls), int(t.yellows), int(t.matches))
        print(f"  team-season openings of {int(t.matches)} matches examined : "
              f"{base['team_season_openings']:,}")
        print(f"  at least {int(t.fouls)} fouls AND at most {int(t.yellows)} yellows : "
              f"{base['as_extreme_both']} ({base['pct_both']:.2f}%)")
        print(f"  ratio at least as lenient                        : "
              f"{base['as_extreme_ratio']} ({base['pct_ratio']:.2f}%)")
        print(f"  openings with zero yellows in {int(t.matches)} matches   : "
              f"{base['zero_yellow_openings']}")


if __name__ == "__main__":
    main()
