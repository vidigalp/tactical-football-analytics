"""The figure for an association that only exists at one level of aggregation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from tfa.viz import theme


def levels(
    leagues: pd.DataFrame,
    blocks: pd.DataFrame,
    path: Path,
    snapshot: str,
) -> list[Path]:
    """Same data, two levels, opposite conclusions.

    Left: one point per league, which is how the association was found and how
    it would have been published. Right: the same leagues split into
    three-season blocks, where every league's own slope runs the other way.

    Both panels share an x and y axis so the reversal is a change in the data
    rather than a change in the framing.
    """
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(theme.DOUBLE_COLUMN + 1.6, 4.0), sharex=True, sharey=True)

    lo = min(leagues.home_gd.min(), blocks.home_gd.min()) - 0.02
    hi = max(leagues.home_gd.max(), blocks.home_gd.max()) + 0.02

    # ---- left: eleven league averages
    left.scatter(leagues.home_gd, leagues.gradient, s=52, zorder=3,
                 color=theme.PALETTE[0], edgecolor="white", linewidth=0.8)
    slope, intercept = np.polyfit(leagues.home_gd, leagues.gradient, 1)
    # Clipped to the observed range. Drawing a fit across the full shared axis
    # implies the relationship was measured over ground no league occupies.
    fit_x = np.array([leagues.home_gd.min(), leagues.home_gd.max()])
    left.plot(fit_x, intercept + slope * fit_x, color=theme.PALETTE[1],
              linewidth=1.8, zorder=2)
    rho = stats.spearmanr(leagues.home_gd, leagues.gradient).statistic

    # Alternate the labels above and below their point. With eleven leagues
    # clustered in a third of the axis, a fixed offset collides every time.
    ordered = leagues.sort_values("home_gd").reset_index(drop=True)
    for position, row in ordered.iterrows():
        above = position % 2 == 0
        left.annotate(
            row.country, xy=(row.home_gd, row.gradient),
            xytext=(0, 9 if above else -15), textcoords="offset points",
            ha="center", va="bottom" if above else "top",
            fontsize=7, color=theme.MUTED)
    left.set_title(f"(A) One point per league   ρ = {rho:+.2f}", fontsize=9.5)
    left.set_ylabel("Booking gradient\n(steeper = more negative)")

    # ---- right: the same leagues, split in time
    within = []
    for _, group in blocks.groupby("lg"):
        if len(group) < 4:
            continue
        b, a = np.polyfit(group.home_gd, group.gradient, 1)
        xs = np.array([group.home_gd.min(), group.home_gd.max()])
        right.plot(xs, a + b * xs, color=theme.PALETTE[0], alpha=0.55,
                   linewidth=1.3, zorder=2)
        within.append(stats.spearmanr(group.home_gd, group.gradient).statistic)
    right.scatter(blocks.home_gd, blocks.gradient, s=16, zorder=3,
                  color=theme.MUTED, alpha=0.45, linewidth=0)

    centred_rho = stats.spearmanr(
        blocks.home_gd - blocks.groupby("lg").home_gd.transform("mean"),
        blocks.gradient - blocks.groupby("lg").gradient.transform("mean"),
    ).statistic
    right.set_title(f"(B) The same leagues, split in time   ρ = {centred_rho:+.2f}", fontsize=9.5)

    negative = sum(1 for r in within if r < 0)
    right.annotate(
        f"one line per league\n{negative} of {len(within)} slope the other way",
        xy=(0.03, 0.04), xycoords="axes fraction", fontsize=7.5,
        color=theme.MUTED, va="bottom")

    for ax in (left, right):
        ax.set_xlabel("Home advantage (goals per match)")
        theme.grid(ax, axis="both")
    left.set_xlim(lo, hi)

    fig.suptitle("An association that exists only between leagues, not within them",
                 fontsize=11, fontweight="bold", x=0.01, ha="left", y=0.99)

    return theme.save(
        fig, path,
        theme.Stamp(
            metric="Booking gradient against home advantage, two levels of aggregation",
            sample=f"{len(leagues)} leagues; {len(blocks)} three-season blocks, 2000-2026",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )
