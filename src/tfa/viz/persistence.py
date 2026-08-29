"""The two-panel replacement figure.

The chart this replaces plotted simulated teams from six competitions on one set
of axes, with no uncertainty, and a boxplot inviting a cross-league comparison of
a ratio that must not be pooled. Both panels here answer the question it was
reaching for, using real data.

Panel A shows where leagues actually sit, because the between-league differences
are large and measurable. Panel B answers the question the original could not:
whether a club's disciplinary profile is a stable trait or a yearly accident.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tfa.viz import theme


def league_phase_and_persistence(
    teams: pd.DataFrame,
    pairs: pd.DataFrame,
    path: Path,
    *,
    season_label: str,
    snapshot: str,
) -> list[Path]:
    """Left: leagues in foul/card space. Right: does a club's rate persist?

    ``teams`` needs Div, country, fouls, yellows, matches for one completed season.
    ``pairs`` needs ``this_season`` and ``next_season`` yellows-per-foul values for
    the same club in consecutive seasons.
    """
    fig, axes = plt.subplots(1, 2, figsize=(theme.DOUBLE_COLUMN + 2.0, 4.4))

    # ---------------- Panel A: leagues, not teams ----------------
    ax = axes[0]
    by_league = teams.groupby(["Div", "country"], as_index=False).agg(
        fouls=("fouls", "sum"), yellows=("yellows", "sum"), matches=("matches", "sum")
    )
    by_league["fouls_pm"] = by_league["fouls"] / by_league["matches"]
    by_league["cards_pm"] = by_league["yellows"] / by_league["matches"]

    xlim = (by_league["fouls_pm"].min() - 1.2, by_league["fouls_pm"].max() + 1.2)
    ax.set_xlim(*xlim)
    ax.set_ylim(by_league["cards_pm"].min() - 0.35, by_league["cards_pm"].max() + 0.35)

    x = np.linspace(*xlim, 100)
    for ratio in (5, 6, 7, 8, 9):
        ax.plot(x, x / ratio, linestyle=(0, (4, 3)), linewidth=0.7,
                color=theme.MUTED, alpha=0.5, zorder=1)
        y_end = xlim[1] / ratio
        if ax.get_ylim()[0] < y_end < ax.get_ylim()[1]:
            ax.annotate(f"{ratio}", xy=(xlim[1], y_end), xytext=(-2, 2),
                        textcoords="offset points", ha="right", va="bottom",
                        fontsize=7, color=theme.MUTED)

    ax.scatter(by_league["fouls_pm"], by_league["cards_pm"], s=46,
               color=theme.PALETTE[0], zorder=3)
    for _, row in by_league.iterrows():
        ax.annotate(row["country"], xy=(row["fouls_pm"], row["cards_pm"]),
                    xytext=(6, -1), textcoords="offset points",
                    fontsize=7.5, color=theme.INK)

    ax.set_xlabel("Fouls per team per match")
    ax.set_ylabel("Yellow cards per team per match")
    ax.set_title(f"(A) Leagues differ, and by a lot  ·  {season_label}")
    theme.grid(ax, axis="both")
    ax.annotate("dashed: fouls per yellow", xy=(0.03, 0.94), xycoords="axes fraction",
                fontsize=7, color=theme.MUTED)

    # ---------------- Panel B: does a club keep its profile? ----------------
    ax = axes[1]
    a = pairs["this_season"].to_numpy(float)
    b = pairs["next_season"].to_numpy(float)

    ax.scatter(1 / a, 1 / b, s=9, alpha=0.30, color=theme.PALETTE[0],
               edgecolor="none", zorder=3)

    lim = (2.5, 13.0)
    ax.plot(lim, lim, color=theme.MUTED, linewidth=0.8, linestyle="--", zorder=2)
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)

    r = float(np.corrcoef(a, b)[0, 1])
    ax.annotate(
        f"r = {r:.2f}   (n = {len(pairs):,} club-season pairs)",
        xy=(0.04, 0.93), xycoords="axes fraction", fontsize=8.5, color=theme.INK,
    )
    ax.annotate(
        "A club's booking rate carries over.\n"
        "The trait is real; a single season\njust cannot measure it precisely.",
        xy=(0.04, 0.68), xycoords="axes fraction", fontsize=7.5, color=theme.MUTED,
    )

    ax.set_xlabel("Fouls per yellow, season t")
    ax.set_ylabel("Fouls per yellow, season t+1")
    ax.set_title("(B) The identity persists across seasons")
    theme.grid(ax, axis="both")

    fig.tight_layout()
    return theme.save(
        fig,
        path,
        theme.Stamp(
            metric=(
                "Left: league totals. Right: same club, consecutive seasons, "
                "completed seasons only"
            ),
            sample=f"{len(teams)} teams; {len(pairs):,} consecutive club-season pairs",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )
