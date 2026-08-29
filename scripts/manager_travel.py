"""Does a manager's disciplinary effect travel between clubs?

The identification: some managers held spells at two or more Primeira Liga clubs
in the window. If the effect is a property of the manager, their spells should
agree with each other. If it is a property of the club, they should not.

Expected yellows are built in two stages, because both confounds are large:

1. **Era.** League fouls-per-yellow fell from about 8.8 to 6.0 over the period,
   so the season's own league rate sets the base.
2. **Match context.** Favourites are booked roughly fifteen percent below what
   their foul count implies, regardless of who they are. A multiplier estimated
   from the whole league by strength band removes it, so a manager moving from a
   mid-table club to a big one does not inherit a spurious effect.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import season_start_year
from tfa.ingest.matches import to_team_match
from tfa.managers import attach, load
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 240)

MIN_SPELL = 15   # matches; below this a spell estimate is mostly noise
STRENGTH_BINS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
BIN_LABELS = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]


def build_expectation(tm: pd.DataFrame) -> pd.DataFrame:
    """Attach expected yellows adjusted for era and match context."""
    lg = tm.groupby("season", as_index=False).agg(
        lg_fouls=("fouls", "sum"), lg_yellows=("yellows", "sum")
    )
    lg["lg_ypf"] = lg.lg_yellows / lg.lg_fouls
    out = tm.merge(lg[["season", "lg_ypf"]], on="season")

    out["band"] = pd.cut(out["strength_diff"], STRENGTH_BINS, labels=BIN_LABELS)
    out["exp_era"] = out["fouls"] * out["lg_ypf"]

    # League-wide context multiplier per strength band.
    ctx = out.groupby("band", observed=True, as_index=False).agg(
        y=("yellows", "sum"), e=("exp_era", "sum"), n=("fouls", "size")
    )
    ctx["multiplier"] = ctx.y / ctx.e
    print("=== League-wide context multiplier by strength band ===")
    print("(booking index of ALL clubs in that situation — the confound itself)")
    print(ctx[["band", "n", "multiplier"]].round(3).to_string(index=False))

    out = out.merge(ctx[["band", "multiplier"]], on="band", how="left")
    out["multiplier"] = out["multiplier"].fillna(1.0)
    out["expected"] = out["exp_era"] * out["multiplier"]
    return out


def ratio_ci(observed: float, expected: float) -> tuple[float, float]:
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
    tm = build_expectation(tm)

    labelled = attach(tm, load("primeira_liga"))
    known = labelled[labelled["manager"].notna()].copy()
    print(f"\n{len(known):,} of {len(labelled):,} team-matches have a named manager "
          f"({100 * len(known) / len(labelled):.0f}%)\n")

    # ---- club baselines, context-adjusted ----
    club = known.groupby("team", as_index=False).agg(
        matches=("fouls", "size"), y=("yellows", "sum"), e=("expected", "sum")
    )
    club["club_index"] = club.y / club.e
    club = club[club.matches >= 80].sort_values("club_index")
    ci = [ratio_ci(y, e) for y, e in zip(club.y, club.e, strict=True)]
    club["lo"], club["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    club["separates"] = (club.lo > 1) | (club.hi < 1)
    print("=== Club booking index, adjusted for era AND match context ===")
    print(club[["team", "matches", "club_index", "lo", "hi", "separates"]]
          .round(3).to_string(index=False))
    print(f"\nclubs separating from 1.0: {int(club.separates.sum())} of {len(club)}")

    # ---- manager-club spells ----
    spell = known.groupby(["manager", "team"], as_index=False).agg(
        matches=("fouls", "size"), y=("yellows", "sum"), e=("expected", "sum"),
        first=("Date", "min"),
    )
    spell = spell[spell.matches >= MIN_SPELL].copy()
    spell["spell_index"] = spell.y / spell.e

    # A manager's effect must be measured against the club WITHOUT them,
    # otherwise a long tenure defines its own baseline and the effect vanishes
    # by construction.
    rows = []
    for _, s in spell.iterrows():
        rest = known[(known.team == s.team) & (known.manager != s.manager)]
        if rest.yellows.sum() < 30:
            continue
        base = rest.yellows.sum() / rest.expected.sum()
        rows.append({**s.to_dict(), "club_base": base,
                     "vs_club": s.spell_index / base})
    spell = pd.DataFrame(rows)

    print(f"\n=== {len(spell)} manager-club spells with {MIN_SPELL}+ matches "
          f"and a comparable club baseline ===")

    multi = spell.groupby("manager").filter(lambda g: g.team.nunique() >= 2)
    movers = sorted(multi.manager.unique())
    print(f"managers with 2+ such spells at DIFFERENT clubs: {len(movers)}")

    if not movers:
        print("\nNot enough movers to test travel. Reporting spells only.")
        print(spell.sort_values("vs_club")[
            ["manager", "team", "matches", "spell_index", "club_base", "vs_club"]
        ].round(3).to_string(index=False))
        return

    print("\n=== Spells of managers who moved between clubs ===")
    show = multi.sort_values(["manager", "first"])[
        ["manager", "team", "matches", "spell_index", "club_base", "vs_club"]]
    print(show.round(3).to_string(index=False))

    # ---- the test ----
    pairs = []
    for mgr, g in multi.groupby("manager"):
        g = g.sort_values("first")
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                a, b = g.iloc[i], g.iloc[j]
                if a.team == b.team:
                    continue
                pairs.append({
                    "manager": mgr, "club_a": a.team, "club_b": b.team,
                    "a": a.vs_club, "b": b.vs_club,
                    "n_a": a.matches, "n_b": b.matches,
                })
    pairs = pd.DataFrame(pairs)

    print(f"\n=== TEST: do a manager's two spells agree? ({len(pairs)} pairs) ===")
    if len(pairs) >= 5:
        r, p = stats.pearsonr(pairs.a, pairs.b)
        rho, prho = stats.spearmanr(pairs.a, pairs.b)
        print(f"  Pearson  r = {r:+.3f}  (p = {p:.3f})")
        print(f"  Spearman r = {rho:+.3f}  (p = {prho:.3f})")

        same_side = ((pairs.a > 1) == (pairs.b > 1)).mean()
        print(f"  spells on the same side of their club baseline: "
              f"{same_side:.0%} ({int(((pairs.a > 1) == (pairs.b > 1)).sum())}/{len(pairs)})"
              f"   — 50% is chance")

        # Null: shuffle which spells are paired, keeping the marginal spread.
        rng = np.random.default_rng(20260829)
        null = [
            stats.pearsonr(pairs.a, rng.permutation(pairs.b.to_numpy()))[0]
            for _ in range(5000)
        ]
        pct = float(np.mean(np.abs(null) >= abs(r)))
        print(f"  permutation p (5,000 shuffles): {pct:.3f}")
        print(f"  null |r| 95th percentile: {np.percentile(np.abs(null), 95):.3f}")
    else:
        print("  too few pairs for a correlation; showing them raw")
        print(pairs.round(3).to_string(index=False))

    # ---- variance decomposition ----
    print("\n=== Where does spell-to-spell variation live? ===")
    spell["log_vs_club"] = np.log(spell.vs_club)
    overall = spell.log_vs_club.var(ddof=1)
    within_mgr = (
        spell.groupby("manager").filter(lambda g: len(g) >= 2)
        .groupby("manager").log_vs_club.var(ddof=1).mean()
    )
    print(f"  variance of log(spell / club baseline) across all spells : {overall:.4f}")
    print(f"  mean variance WITHIN a manager (2+ spells)               : {within_mgr:.4f}")
    if within_mgr >= overall:
        print("  -> a manager's own spells vary as much as different managers do.")
        print("     No evidence the effect belongs to the manager.")
    else:
        share = 1 - within_mgr / overall
        print(f"  -> {share:.0%} of spell variation is between managers rather than within.")


if __name__ == "__main__":
    main()
