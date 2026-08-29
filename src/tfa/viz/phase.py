"""The tactical phase space, done honestly.

Fouls per match against cards per match, with iso-lines of constant cards-per-foul.
The two-dimensional form is the point: a high fouls-per-card ratio can come from
committing unusually many fouls or from receiving unusually few cards, and those
are different tactical stories that a single ranked number hides.

What separates this from the version that motivated it:

* estimates are shrunk toward the league mean, so a team is not placed on the
  strength of three matches;
* every point carries a credible interval;
* one league at a time, because the ratio must not be pooled across leagues;
* real data, with the sample size stated on the figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tfa.viz import theme


def _iso_lines(ax: plt.Axes, ratios: tuple[float, ...], xlim: tuple[float, float]) -> None:
    """Lines of constant fouls-per-card: y = x / ratio."""
    x = np.linspace(*xlim, 100)
    for ratio in ratios:
        y = x / ratio
        ax.plot(x, y, linestyle=(0, (4, 3)), linewidth=0.7,
                color=theme.MUTED, alpha=0.55, zorder=1)
        # Label at the right edge, only if the line is still on the axes there.
        y_end = xlim[1] / ratio
        if ax.get_ylim()[0] < y_end < ax.get_ylim()[1]:
            ax.annotate(
                f"{ratio:g} fouls/card",
                xy=(xlim[1], y_end), xytext=(-4, 3), textcoords="offset points",
                ha="right", va="bottom", fontsize=7, color=theme.MUTED, zorder=1,
            )


def phase_space(
    teams: pd.DataFrame,
    path: Path,
    *,
    league: str,
    season_label: str,
    snapshot: str,
    label_extremes: int = 3,
) -> list[Path]:
    """Shrunken phase space for a single league-season, with intervals."""
    d = teams.sort_values("fouls_per_match_shrunk").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 4.8))

    xlim = (
        float(d["fouls_per_match_lo"].min()) - 0.8,
        float(d["fouls_per_match_hi"].max()) + 0.8,
    )
    ylim = (
        max(0.0, float(d["cards_per_match_lo"].min()) - 0.25),
        float(d["cards_per_match_hi"].max()) + 0.25,
    )
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    _iso_lines(ax, (3, 4, 5, 6, 8, 12), xlim)

    ax.errorbar(
        d["fouls_per_match_shrunk"], d["cards_per_match_shrunk"],
        xerr=[
            d["fouls_per_match_shrunk"] - d["fouls_per_match_lo"],
            d["fouls_per_match_hi"] - d["fouls_per_match_shrunk"],
        ],
        yerr=[
            d["cards_per_match_shrunk"] - d["cards_per_match_lo"],
            d["cards_per_match_hi"] - d["cards_per_match_shrunk"],
        ],
        fmt="o", markersize=4.5, color=theme.PALETTE[0],
        ecolor=theme.PALETTE[0], elinewidth=0.8, alpha=0.65, capsize=0, zorder=3,
    )

    # Name only the teams at the extremes of the ratio, so the figure stays
    # readable and no team is singled out for its position alone.
    ranked = d.sort_values("fouls_per_card_shrunk")
    for _, row in pd.concat([ranked.head(label_extremes), ranked.tail(label_extremes)]).iterrows():
        ax.annotate(
            row["team"],
            xy=(row["fouls_per_match_shrunk"], row["cards_per_match_shrunk"]),
            xytext=(5, 4), textcoords="offset points",
            fontsize=7.5, color=theme.INK, zorder=4,
        )

    ax.set_xlabel("Fouls committed per match")
    ax.set_ylabel("Cards received per match")
    ax.set_title(f"{league}, {season_label}")
    theme.grid(ax, axis="both")

    # If a dimension has no detectable between-team variance, say so on the
    # figure. Eighteen identical points otherwise read as a plotting error
    # rather than as the finding it actually is.
    undetectable = [
        name
        for name, column in (("fouls", "fouls_detectable"), ("cards", "cards_detectable"))
        if column in d and not bool(d[column].iloc[0])
    ]
    if undetectable:
        ax.annotate(
            "No detectable between-team variation in "
            + " or ".join(undetectable)
            + " at this sample size:\nthe observed spread is fully explained by "
            "sampling noise, so every team collapses to the league mean.",
            xy=(0.5, 0.06), xycoords="axes fraction", ha="center", va="bottom",
            fontsize=8, color=theme.PALETTE[1],
        )

    median_matches = int(d["matches"].median())
    return theme.save(
        fig,
        path,
        theme.Stamp(
            metric="Shrunken team rates, 95% credible intervals. Dashed: constant fouls per card",
            sample=f"{len(d)} teams, median {median_matches} matches each",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )


def raw_versus_shrunk(
    teams: pd.DataFrame,
    path: Path,
    *,
    league: str,
    season_label: str,
    snapshot: str,
) -> list[Path]:
    """What happens to a fouls-per-card ranking once the sample is respected.

    The left column is the ranking a spreadsheet produces. The right column is
    the same teams after shrinkage. The lines between them are the finding.
    """
    d = teams.dropna(subset=["fouls_per_card"]).copy()
    d = d.sort_values("fouls_per_card", ascending=False).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 5.0))

    for _, row in d.iterrows():
        ax.plot(
            [0, 1], [row["fouls_per_card"], row["fouls_per_card_shrunk"]],
            color=theme.MUTED, alpha=0.35, linewidth=0.8, zorder=1,
        )

    ax.scatter([0] * len(d), d["fouls_per_card"], s=30,
               color=theme.PALETTE[1], zorder=3, label="raw ratio")
    ax.scatter([1] * len(d), d["fouls_per_card_shrunk"], s=30, marker="s",
               color=theme.PALETTE[0], zorder=3, label="after shrinkage")

    top = d.iloc[0]
    ax.annotate(
        # ASCII only: the configured font stack has no arrow glyph, and a
        # missing glyph renders as a tofu box in the published figure.
        f"{top['team']}: {top['fouls_per_card']:.1f} down to "
        f"{top['fouls_per_card_shrunk']:.1f}",
        xy=(0, top["fouls_per_card"]), xytext=(0.06, top["fouls_per_card"]),
        fontsize=8, color=theme.INK, va="center",
    )

    ax.set_xlim(-0.25, 1.45)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["what the raw\nnumbers say", "what the sample\nsupports"])
    ax.set_ylabel("Fouls per card")
    ax.set_title(f"{league}, {season_label}")
    ax.legend(loc="upper right", frameon=False)
    theme.grid(ax, axis="y")

    median_matches = int(d["matches"].median())
    spread_raw = d["fouls_per_card"].max() - d["fouls_per_card"].min()
    spread_shrunk = d["fouls_per_card_shrunk"].max() - d["fouls_per_card_shrunk"].min()

    return theme.save(
        fig,
        path,
        theme.Stamp(
            metric=(
                f"Fouls per card. Spread collapses from {spread_raw:.1f} to "
                f"{spread_shrunk:.1f} once sample size is respected"
            ),
            sample=f"{len(d)} teams, median {median_matches} matches each",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )
