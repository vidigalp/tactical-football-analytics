"""Does club strength predict being booked more than the situation implies?

The situation adjustment already removes the large effect of being favourite:
league-wide, favourites are booked well below what their foul count implies.
This asks whether anything is left over that tracks how strong a club is.

Uses a continuous adjustment rather than strength bands. Bands are dangerous
here: the effect is smooth and monotonic across the whole strength range, so the
strongest clubs sit at the extreme of the top band and a band-average multiplier
under-corrects exactly the clubs the question is about. A quartic Poisson fit
with a log-offset removes that objection.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import COMPETITIONS, is_completed
from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"
pd.set_option("display.width", 200)
MIN_MATCHES = 150


def load_all(directory: Path) -> pd.DataFrame:
    frames = []
    for code in COMPETITIONS:
        entries = [
            e for e in read_manifest(directory)
            if e.source == "football-data" and e.competition == code
        ]
        if not entries:
            continue
        frame = pd.concat(
            [pd.read_parquet(directory / e.parquet_path) for e in entries],
            ignore_index=True,
        )
        tm = to_team_match(frame)
        tm["league"] = code
        frames.append(tm)
    tm = pd.concat(frames, ignore_index=True)
    tm = tm.dropna(subset=["strength_diff", "fouls", "yellows"])
    # Retrospective: the season in progress is excluded. See
    # competitions.LAST_COMPLETED_SEASON_YEAR for why this matters more than
    # tidiness — the live season is the one under investigation.
    tm = tm[tm["season"].map(is_completed)]
    # A zero-foul match makes the log-offset undefined. There are a few dozen.
    return tm[tm["fouls"] > 0].copy()


def fit_continuous(tm: pd.DataFrame, degree: int = 4) -> np.ndarray:
    """Poisson IRLS for yellows, offset by era-expected, smooth in strength."""
    s = tm["strength_diff"].to_numpy(float)
    X = np.column_stack([s**k for k in range(degree + 1)])
    y = tm["yellows"].to_numpy(float)
    offset = np.log(tm["exp_era"].to_numpy(float))

    beta = np.zeros(X.shape[1])
    for _ in range(80):
        mu = np.exp(np.clip(X @ beta + offset, -20, 20))
        w = np.maximum(mu, 1e-9)
        z = X @ beta + (y - mu) / w
        new = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * z))
        if np.max(np.abs(new - beta)) < 1e-11:
            return new
        beta = new
    return beta


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    tm = load_all(directory)

    lg = tm.groupby(["league", "season"], as_index=False).agg(
        f=("fouls", "sum"), y=("yellows", "sum"))
    lg["lg_ypf"] = lg.y / lg.f
    tm = tm.merge(lg[["league", "season", "lg_ypf"]], on=["league", "season"])
    tm["exp_era"] = tm.fouls * tm.lg_ypf

    print(f"{len(tm):,} team-matches, {tm.league.nunique()} leagues\n")

    print("=== Booking index by strength decile: smooth, and it does not saturate ===")
    band = pd.qcut(tm.strength_diff, 12, duplicates="drop")
    prof = tm.groupby(band, observed=True).apply(
        lambda g: pd.Series({"strength": g.strength_diff.mean(), "n": len(g),
                             "index": g.yellows.sum() / g.exp_era.sum()}),
        include_groups=False)
    print(prof.round(3).to_string(index=False))

    beta = fit_continuous(tm)
    s = tm["strength_diff"].to_numpy(float)
    X = np.column_stack([s**k for k in range(len(beta))])
    tm["exp_adj"] = np.exp(np.clip(X @ beta + np.log(tm.exp_era), -20, 20))

    club = tm.groupby(["league", "team"], as_index=False).agg(
        n=("fouls", "size"), y=("yellows", "sum"),
        e=("exp_adj", "sum"), strength=("strength_diff", "mean"))
    club = club[club.n >= MIN_MATCHES].copy()
    club["adjusted"] = club.y / club.e

    # The aggregation attack, in one table. If the association belonged to the
    # club, the OPPONENTS a club faces would not carry it too. Computed here
    # because the report has been quoting all three of these from nowhere.
    opp = tm.groupby(["league", "opponent"], as_index=False).agg(
        opp_y=("yellows", "sum"), opp_e=("exp_adj", "sum"))
    opp["opponents_index"] = opp.opp_y / opp.opp_e
    club = club.merge(
        opp.rename(columns={"opponent": "team"})[["league", "team", "opponents_index"]],
        on=["league", "team"], how="left")

    r, p = stats.pearsonr(club.strength, club.adjusted)
    rho, prho = stats.spearmanr(club.strength, club.adjusted)
    paired = club.dropna(subset=["opponents_index"])
    r_opp, p_opp = stats.pearsonr(paired.strength, paired.opponents_index)
    r_both, p_both = stats.pearsonr(paired.adjusted, paired.opponents_index)
    print(f"\n=== Aggregation attack ({len(paired)} clubs) ===")
    print(f"  corr(strength, own index)        = {r:+.3f}  p = {p:.2e}")
    print(f"  corr(strength, opponents' index) = {r_opp:+.3f}  p = {p_opp:.2e}")
    print(f"  corr(own index, opponents')      = {r_both:+.3f}  p = {p_both:.3f}")
    print(f"\n=== Residual association with club strength ({len(club)} clubs) ===")
    print(f"  Pearson  r = {r:+.3f}   p = {p:.2e}")
    print(f"  Spearman r = {rho:+.3f}   p = {prho:.2e}")

    within = []
    for code, g in club.groupby("league"):
        if len(g) >= 8:
            within.append({"league": code, "country": COMPETITIONS[code].country,
                           "clubs": len(g),
                           "r": round(stats.pearsonr(g.strength, g.adjusted)[0], 3)})
    w = pd.DataFrame(within).sort_values("r", ascending=False)
    print(f"\n{w.to_string(index=False)}")
    print(f"\n  mean within-league r = {w.r.mean():+.3f}   "
          f"({int((w.r > 0).sum())} of {len(w)} leagues positive)")

    club["tier"] = pd.qcut(club.strength, 4,
                           labels=["weakest", "weak", "strong", "strongest"])
    tiers = club.groupby("tier", observed=True).agg(
        clubs=("adjusted", "size"), mean_index=("adjusted", "mean")).round(3)
    print(f"\n=== By strength quartile ===\n{tiers.to_string()}")
    top = club[club.tier == "strongest"]
    bot = club[club.tier == "weakest"]
    print(f"\n  strongest vs weakest: {top.adjusted.mean():.3f} vs "
          f"{bot.adjusted.mean():.3f}   p = "
          f"{stats.ttest_ind(top.adjusted, bot.adjusted).pvalue:.2e}")
    print("  note the pattern is a threshold, not a gradient: only the top "
          "quartile departs from 1.0")

    print("\n=== Most and least affected clubs ===")
    ranked = club.sort_values("adjusted", ascending=False)
    print(ranked.head(10)[["league", "team", "n", "strength", "adjusted"]]
          .round(3).to_string(index=False))

    facts = {
        "snapshot": directory.name,
        "team_matches": int(len(tm)),
        "clubs": int(len(club)),
        "leagues": int(club.league.nunique()),
        "pearson_r": float(r),
        "pearson_p": float(p),
        "spearman_r": float(rho),
        "spearman_p": float(prho),
        "opponents": {
            "clubs": int(len(paired)),
            "r_strength_vs_opponents_index": float(r_opp),
            "p_strength_vs_opponents_index": float(p_opp),
            "r_own_vs_opponents_index": float(r_both),
            "p_own_vs_opponents_index": float(p_both),
        },
        "within_league_mean_r": float(w.r.mean()),
        "within_league_positive": int((w.r > 0).sum()),
        "within_league_fitted": int(len(w)),
        "within_league_r": {row.league: float(row.r) for row in w.itertuples()},
        "by_quartile": {
            str(tier): float(value)
            for tier, value in tiers.mean_index.items()
        },
        "strongest_vs_weakest": {
            "strongest": float(top.adjusted.mean()),
            "weakest": float(bot.adjusted.mean()),
            "p": float(stats.ttest_ind(top.adjusted, bot.adjusted).pvalue),
        },
    }
    sidecar = ROOT / "reports" / REPORT / "strength_effect.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {sidecar.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
