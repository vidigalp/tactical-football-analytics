"""Per-manager discipline profile for one club.

Every rate is expressed **relative to that season's league mean**, because
league discipline has moved a long way over the period: fouls per yellow fell
from about 8.8 in the early 2000s to about 6.0 today. A manager holding a long
tenure would otherwise appear to change a team's behaviour when nothing but the
refereeing regime had shifted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from scipy import stats

from tfa.competitions import season_start_year
from tfa.ingest.matches import to_team_match
from tfa.managers import attach, load
from tfa.snapshot import read_manifest
from tfa.stats.shrinkage import beta_binomial_prior, shrink_beta_binomial

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 220)


def league_baselines(team_matches: pd.DataFrame) -> pd.DataFrame:
    """League mean rates per season, used as the yardstick."""
    g = team_matches.groupby("season", as_index=False).agg(
        lg_fouls=("fouls", "sum"), lg_yellows=("yellows", "sum"),
        lg_matches=("fouls", "size"),
    )
    g["lg_fouls_pm"] = g.lg_fouls / g.lg_matches
    g["lg_yellows_pm"] = g.lg_yellows / g.lg_matches
    g["lg_ypf"] = g.lg_yellows / g.lg_fouls
    return g


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--club", default="Porto")
    parser.add_argument("--league", default="P1")
    args = parser.parse_args()

    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [
        e for e in read_manifest(directory)
        if e.source == "football-data" and e.competition == args.league
    ]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    tm = to_team_match(matches)
    base = league_baselines(tm)

    labelled = attach(tm, load("primeira_liga"))
    club = labelled[labelled["team"] == args.club].merge(base, on="season", how="left")

    print(f"=== {args.club} — {len(club)} matches, "
          f"{club['manager'].notna().sum()} with a named manager "
          f"({100 * club['manager'].notna().mean():.0f}%) ===\n")

    known = club[club["manager"].notna()].copy()

    # Expected yellows if this team fouled the same but was booked at its
    # league's own rate that season. The ratio of actual to expected is the
    # era-free quantity.
    known["exp_yellows"] = known["fouls"] * known["lg_ypf"]

    agg = known.groupby("manager", as_index=False).agg(
        matches=("fouls", "size"),
        first=("Date", "min"),
        last=("Date", "max"),
        fouls=("fouls", "sum"),
        yellows=("yellows", "sum"),
        exp_yellows=("exp_yellows", "sum"),
        lg_fouls_pm=("lg_fouls_pm", "mean"),
    )
    agg = agg[agg["matches"] >= 5].sort_values("first")

    agg["fouls_pm"] = agg.fouls / agg.matches
    agg["fouls_vs_league"] = agg.fouls_pm / agg.lg_fouls_pm
    agg["ypf"] = agg.yellows / agg.fouls
    agg["fouls_per_yellow"] = agg.fouls / agg.yellows
    # Booking index: 1.0 means booked exactly as often as the league books a
    # foul that season. Below 1 means fewer cards than the fouls imply.
    agg["booking_index"] = agg.yellows / agg.exp_yellows

    # Poisson interval on the ratio of observed to expected yellows.
    lo, hi = [], []
    for y, e in zip(agg.yellows, agg.exp_yellows, strict=True):
        a = stats.chi2.ppf(0.025, 2 * y) / 2 if y > 0 else 0.0
        b = stats.chi2.ppf(0.975, 2 * (y + 1)) / 2
        lo.append(a / e)
        hi.append(b / e)
    agg["bi_lo"], agg["bi_hi"] = lo, hi

    show = ["manager", "matches", "first", "last", "fouls_pm", "fouls_vs_league",
            "fouls_per_yellow", "booking_index", "bi_lo", "bi_hi"]
    out = agg[show].copy()
    out["first"] = out["first"].dt.date
    out["last"] = out["last"].dt.date
    print(out.round(3).to_string(index=False))

    print("\nbooking_index: yellows received / yellows expected at the league's "
          "own rate for that many fouls, that season.")
    print("1.00 = exactly as the league books. Interval is 95% Poisson.\n")

    # Does any manager separate from 1.0?
    sep = agg[(agg.bi_lo > 1.0) | (agg.bi_hi < 1.0)]
    if len(sep):
        print("Managers whose interval EXCLUDES the league rate:")
        print(sep[["manager", "matches", "booking_index", "bi_lo", "bi_hi"]]
              .round(3).to_string(index=False))
    else:
        print("No manager's interval excludes the league rate.")

    # Shrunken team-level view for comparison.
    prior = beta_binomial_prior(agg.yellows, agg.fouls)
    est = shrink_beta_binomial(agg.yellows, agg.fouls, prior)
    print(f"\nBetween-manager variance detectable? {prior.detectable_variance}")
    print(f"prior sample size n0 = {prior.prior_sample_size:,.0f} fouls "
          f"(~{prior.prior_sample_size / agg.fouls_pm.mean():.0f} matches for r=0.5)")
    agg["shrunk_fpy"] = 1.0 / est["shrunk"].to_numpy()
    print(agg[["manager", "matches", "fouls_per_yellow", "shrunk_fpy"]]
          .round(2).to_string(index=False))

    # Within the longest tenure, does the metric drift with the league?
    longest = agg.sort_values("matches").iloc[-1]["manager"]
    span = known[known["manager"] == longest].copy()
    span["yr"] = span["season"].map(season_start_year)
    per_season = span.groupby("yr").agg(
        matches=("fouls", "size"), fouls=("fouls", "sum"), yellows=("yellows", "sum"),
        lg_ypf=("lg_ypf", "mean"),
    )
    per_season["fouls_per_yellow"] = (per_season.fouls / per_season.yellows).round(2)
    per_season["league_fpy"] = (1 / per_season.lg_ypf).round(2)
    per_season["booking_index"] = (
        per_season.yellows / (per_season.fouls * per_season.lg_ypf)
    ).round(3)
    print(f"\n=== Within {longest}'s tenure, season by season ===")
    print(per_season[["matches", "fouls_per_yellow", "league_fpy", "booking_index"]]
          .to_string())


if __name__ == "__main__":
    main()
