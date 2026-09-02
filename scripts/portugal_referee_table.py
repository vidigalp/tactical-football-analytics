"""Study 02's headline table: Portuguese clubs after era, situation and referee.

Written because a freshness review found the table had no script behind it. The
figures were right -- an independent rebuild landed within 0.004 of every one --
but a headline nobody can re-derive is exactly the failure that put a
wrong-signed correlation into this study once already. Every number study 02
publishes now traces to committed code.

Portugal names no referee in football-data.co.uk, so the officials come from
data/managers/primeira_liga_referees.csv, harvested from zerozero.pt and joined
on the scoreline rather than on names alone.

Run: uv run python scripts/portugal_referee_table.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import is_completed
from tfa.ingest.referees import join_to_matches

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"

#: Pre-match role, from the devigged odds. Symmetric about zero by construction.
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]

#: Below this an official's own multiplier is too noisy to adjust anything by.
MIN_REF_MATCHES = 40

#: Team-matches a club needs before it is ranked at all.
MIN_CLUB_MATCHES = 80


def interval(observed: float, expected: float) -> tuple[float, float]:
    """Poisson interval on a ratio of observed to expected counts."""
    low = stats.chi2.ppf(0.025, 2 * observed) / 2 if observed > 0 else 0.0
    high = stats.chi2.ppf(0.975, 2 * (observed + 1)) / 2
    return low / expected, high / expected


def load() -> pd.DataFrame:
    """Portuguese team-matches with the official attached where known."""
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    matches = pd.read_parquet(
        next(snapshot.glob("football-data__P1__*.parquet")))
    matches = matches.dropna(subset=["HF", "AF", "HY", "AY", "strength_diff"])
    # Retrospective: the season in progress is excluded. See
    # competitions.LAST_COMPLETED_SEASON_YEAR for why this matters more than
    # tidiness — the live season is the one under investigation.
    matches = matches[matches["season"].map(is_completed)]

    referees = pd.read_csv(ROOT / "data" / "managers" / "primeira_liga_referees.csv")
    joined, _unmatched = join_to_matches(referees, matches)

    home = pd.DataFrame({
        "season": joined.season, "team": joined.HomeTeam,
        "fouls": joined.HF, "yellows": joined.HY,
        "strength": joined.strength_diff, "referee": joined.referee,
    })
    away = pd.DataFrame({
        "season": joined.season, "team": joined.AwayTeam,
        "fouls": joined.AF, "yellows": joined.AY,
        "strength": -joined.strength_diff, "referee": joined.referee,
    })
    return pd.concat([home, away], ignore_index=True)


def add_expectations(teams: pd.DataFrame) -> pd.DataFrame:
    """Three expectations, each adding one adjustment on top of the last."""
    teams = teams.copy()

    # Era: the league's own cards-per-foul rate that season, so a league-wide
    # drift in strictness is not read as a club changing behaviour.
    rate = teams.groupby("season").apply(
        lambda g: g.yellows.sum() / g.fouls.sum(), include_groups=False).rename("rate")
    teams = teams.merge(rate, left_on="season", right_index=True)
    teams["exp_era"] = teams.fouls * teams.rate

    # Situation: how the league as a whole is carded in that pre-match role.
    teams["band"] = pd.cut(teams.strength, BANDS, labels=NAMES)
    band = teams.groupby("band", observed=True).apply(
        lambda g: g.yellows.sum() / g.exp_era.sum(), include_groups=False).rename("band_mult")
    teams = teams.merge(band, left_on="band", right_index=True, how="left")
    teams["exp_situation"] = teams.exp_era * teams.band_mult.fillna(1.0)

    return teams


def referee_multipliers(teams: pd.DataFrame, *, exclude: str | None = None) -> pd.Series:
    """Each official's own tendency, measured against the situation expectation.

    ``exclude`` drops one club before estimating. A club that appears often with
    one official would otherwise help set the very baseline it is judged
    against, and a real club effect would partly cancel itself out.
    """
    known = teams[teams.referee.notna()]
    if exclude is not None:
        known = known[known.team != exclude]
    counts = known.groupby("referee").size()
    eligible = counts[counts >= MIN_REF_MATCHES].index
    subset = known[known.referee.isin(eligible)]
    return subset.groupby("referee").apply(
        lambda g: g.yellows.sum() / g.exp_situation.sum(), include_groups=False)


def poisson_two_sided(observed: int, expected: float) -> float:
    """Two-sided Poisson probability of a count this far from *expected*.

    The doubled one-tailed tail, which is the convention the interval in
    :func:`interval` already assumes, so the screen and the interval cannot
    disagree about which clubs are extreme.
    """
    if expected <= 0:
        return 1.0
    if observed >= expected:
        tail = stats.poisson.sf(observed - 1, expected)
    else:
        tail = stats.poisson.cdf(observed, expected)
    return float(min(1.0, 2 * tail))


def main() -> None:
    teams = add_expectations(load())
    multipliers = referee_multipliers(teams)

    # Leave-one-club-out: each club is judged against officials measured without
    # it. Done per club rather than once globally, which is the whole point.
    rows = []
    for team, group in teams.groupby("team"):
        if len(group) < MIN_CLUB_MATCHES:
            continue
        others = referee_multipliers(teams, exclude=str(team))
        mult = group.referee.map(others)
        # An official without enough matches adjusts nothing rather than being
        # dropped: discarding those rows would shrink every club's sample.
        rows.append({
            "team": team,
            "n": len(group),
            "fouls": group.fouls.sum(),
            "yellows": group.yellows.sum(),
            "e_era": group.exp_era.sum(),
            "e_situation": group.exp_situation.sum(),
            "e_referee": (group.exp_situation * mult.fillna(1.0)).sum(),
            "ref_draw": float(mult.mean()),
        })
    clubs = pd.DataFrame(rows).set_index("team")
    clubs["raw"] = clubs.yellows / clubs.e_era
    clubs["situation"] = clubs.yellows / clubs.e_situation
    clubs["referee"] = clubs.yellows / clubs.e_referee
    bounds = [interval(y, e) for y, e in zip(clubs.yellows, clubs.e_referee, strict=True)]
    clubs["lo"] = [b[0] for b in bounds]
    clubs["hi"] = [b[1] for b in bounds]
    clubs["separates"] = (clubs.lo > 1.0) | (clubs.hi < 1.0)

    # The multiplicity screen. Twenty-six clubs tested and the extreme one
    # reported is how a finding is manufactured, so the correction belongs in
    # the script that produces the table rather than in the prose beside it.
    # These p-values were previously typed into the report by hand.
    clubs["p_raw"] = [
        poisson_two_sided(int(y), float(e))
        for y, e in zip(clubs.yellows, clubs.e_referee, strict=True)
    ]
    order = np.argsort(clubs.p_raw.to_numpy())
    ranked = clubs.p_raw.to_numpy()[order]
    m = len(ranked)
    # Benjamini-Hochberg, enforcing monotonicity from the largest p downward.
    adjusted = np.minimum.accumulate(
        (ranked * m / np.arange(1, m + 1))[::-1]
    )[::-1].clip(max=1.0)
    bh = np.empty(m)
    bh[order] = adjusted
    clubs["p_bh"] = bh
    clubs["p_bonferroni"] = (clubs.p_raw * m).clip(upper=1.0)
    clubs = clubs.sort_values("referee", ascending=False)

    print(f"{len(teams):,} team-matches, "
          f"{teams.referee.notna().mean():.1%} with a known official")
    print(f"officials with {MIN_REF_MATCHES}+ matches: {len(multipliers)}, "
          f"multiplier {multipliers.min():.2f} to {multipliers.max():.2f}\n")
    print(clubs[["n", "raw", "situation", "referee", "lo", "hi", "ref_draw", "separates"]]
          .to_string(float_format=lambda v: f"{v:.3f}"))
    separating = clubs[clubs.separates]
    print(f"\nseparating after era + situation + referee: "
          f"{len(separating)} of {len(clubs)}")
    print(f"referee draw across clubs: {clubs.ref_draw.min():.3f} "
          f"to {clubs.ref_draw.max():.3f}")

    screen = clubs.sort_values("p_raw")[["referee", "p_raw", "p_bh", "p_bonferroni"]]
    print("\nmultiplicity screen, most extreme first:")
    print(screen.head(5).to_string(
        float_format=lambda v: f"{v:.5f}" if v < 0.001 else f"{v:.3f}"))
    print(f"  uncorrected p < 0.05: {int((clubs.p_raw < 0.05).sum())} of {len(clubs)}")
    print(f"  surviving BH at FDR 0.10: {int((clubs.p_bh < 0.10).sum())}")

    facts = {
        "team_matches": int(len(teams)),
        "referee_known_share": float(teams.referee.notna().mean()),
        "officials": int(len(multipliers)),
        "referee_multiplier_min": float(multipliers.min()),
        "referee_multiplier_max": float(multipliers.max()),
        "clubs": int(len(clubs)),
        "separating": int(len(separating)),
        "naive_significant": int((clubs.p_raw < 0.05).sum()),
        "bh_surviving": int((clubs.p_bh < 0.10).sum()),
        "bh_fdr": 0.10,
        "ref_draw_min": float(clubs.ref_draw.min()),
        "ref_draw_max": float(clubs.ref_draw.max()),
        "table": {
            team: {
                "raw": round(float(row.raw), 3),
                "situation": round(float(row.situation), 3),
                "referee": round(float(row.referee), 3),
                "lo": round(float(row.lo), 3),
                "hi": round(float(row.hi), 3),
                "p_raw": float(row.p_raw),
                "p_bh": float(row.p_bh),
                "p_bonferroni": float(row.p_bonferroni),
            }
            for team, row in clubs.iterrows()
        },
    }
    out = ROOT / "reports" / REPORT / "referee_table.json"
    out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
