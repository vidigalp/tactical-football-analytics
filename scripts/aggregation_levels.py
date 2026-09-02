"""Booking gradient against home advantage, at two levels of aggregation.

Answers study 02's open question about absolute versus relative league quality,
negatively. The association is clear across eleven league averages and absent
within leagues over time, which makes it a property of the aggregation rather
than of football.

Run: uv run python scripts/aggregation_levels.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import is_completed, season_start_year
from tfa.viz import aggregation, theme

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"

#: Three seasons per point. One season cannot estimate a slope: the standard
#: error swamps the between-league spread the figure is about.
BLOCK = 3
MIN_TEAM_MATCHES = 600

#: Blocks a league needs before its own slope over time is fitted at all. Three
#: points through a line is a gesture rather than an estimate. This threshold was
#: applied in the published study but never written down; it is recorded here
#: because it is what sets the denominator of "n of the six leagues".
MIN_BLOCKS_FOR_SLOPE = 4

COUNTRY = {"E0": "England", "I1": "Italy", "SP1": "Spain", "D1": "Germany",
           "F1": "France", "P1": "Portugal", "B1": "Belgium",
           "N1": "Netherlands", "T1": "Turkey", "G1": "Greece", "SC0": "Scotland"}


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


def gradient(matches: pd.DataFrame) -> float:
    """Change in log booking index per unit of pre-match strength.

    Poisson regression with cards-expected-from-fouls as a fixed offset, so the
    coefficient is about the rate per foul rather than the count of fouls.
    """
    strength = np.concatenate([matches.strength_diff.to_numpy(float),
                               -matches.strength_diff.to_numpy(float)])
    fouls = np.concatenate([matches.HF.to_numpy(float), matches.AF.to_numpy(float)])
    cards = np.concatenate([matches.HY.to_numpy(float), matches.AY.to_numpy(float)])

    offset = np.log(np.maximum(cards.sum() / fouls.sum() * fouls, 1e-9))
    design = np.column_stack([np.ones(len(strength)), strength])
    beta = np.zeros(2)
    for _ in range(60):
        mu = np.exp(np.clip(design @ beta + offset, -20, 20))
        weighted = design.T * mu
        working = design @ beta + (cards - mu) / np.maximum(mu, 1e-9)
        step = np.linalg.solve(weighted @ design, weighted @ working)
        if np.max(np.abs(step - beta)) < 1e-10:
            return float(step[1])
        beta = step
    return float(beta[1])


def main() -> None:
    theme.apply()
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    matches = load(snapshot)

    leagues = pd.DataFrame([
        {"lg": lg, "country": COUNTRY[lg], "gradient": gradient(m),
         "home_gd": float((m.FTHG - m.FTAG).mean())}
        for lg, m in matches.groupby("lg")
    ])

    rows = []
    for lg, m in matches.groupby("lg"):
        for start in range(int(m.yr.min()), int(m.yr.max()) + 1, BLOCK):
            block = m[(m.yr >= start) & (m.yr < start + BLOCK)]
            if len(block) * 2 < MIN_TEAM_MATCHES:
                continue
            rows.append({"lg": lg, "yr": start + BLOCK / 2,
                         "gradient": gradient(block),
                         "home_gd": float((block.FTHG - block.FTAG).mean())})
    blocks = pd.DataFrame(rows)

    between = stats.spearmanr(leagues.home_gd, leagues.gradient)
    within = stats.spearmanr(
        blocks.home_gd - blocks.groupby("lg").home_gd.transform("mean"),
        blocks.gradient - blocks.groupby("lg").gradient.transform("mean"))
    pooled = stats.spearmanr(blocks.home_gd, blocks.gradient)

    # Sign of each league's own slope over time. The claim in the report and in
    # METHODS is not only that the within-league correlation is near zero, but
    # that individual leagues slope in both directions — so the count has to be
    # computed rather than remembered.
    slopes = {}
    for lg, g in blocks.groupby("lg"):
        if len(g) < MIN_BLOCKS_FOR_SLOPE:
            continue
        slopes[lg] = float(np.polyfit(g.home_gd, g.gradient, 1)[0])
    negative = sum(1 for v in slopes.values() if v < 0)

    print(f"leagues: {len(leagues)}   blocks: {len(blocks)}")
    print(f"  between leagues   rho={between.statistic:+.3f}  p={between.pvalue:.3f}")
    print(f"  blocks pooled     rho={pooled.statistic:+.3f}  p={pooled.pvalue:.3f}")
    print(f"  within league     rho={within.statistic:+.3f}  p={within.pvalue:.3f}")
    print(f"  leagues with enough blocks to fit a line: {len(slopes)}, "
          f"of which {negative} slope negative")

    facts = {
        "snapshot": snapshot.name,
        "leagues": int(len(leagues)),
        "blocks": int(len(blocks)),
        "block_seasons": BLOCK,
        "between_leagues": {"rho": float(between.statistic), "p": float(between.pvalue)},
        "blocks_pooled": {"rho": float(pooled.statistic), "p": float(pooled.pvalue)},
        "within_league": {"rho": float(within.statistic), "p": float(within.pvalue)},
        "league_slopes": slopes,
        "leagues_fitted": int(len(slopes)),
        "min_blocks_for_slope": MIN_BLOCKS_FOR_SLOPE,
        "leagues_sloping_negative": int(negative),
        "gradient_by_league": {
            row.lg: {"gradient": float(row.gradient), "home_gd": float(row.home_gd)}
            for row in leagues.itertuples()
        },
    }
    sidecar = ROOT / "reports" / REPORT / "aggregation.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"wrote {sidecar.relative_to(ROOT)}")

    out = ROOT / "reports" / REPORT / "figures"
    for written in aggregation.levels(leagues, blocks, out / "fig7-aggregation-levels",
                                      snapshot.name):
        print(f"wrote {written.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
