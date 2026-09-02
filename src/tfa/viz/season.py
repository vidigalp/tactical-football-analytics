"""The season in progress: every club, with the uncertainty made visible.

A two-row table shows that one club is unusual. It cannot show that the club is
unusual *against the spread of every other club*, which is the only reading that
survives the multiplicity problem. So the whole league goes on one axis with its
intervals, and a reader sees both the outlier and how wide four matches leaves
every estimate.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from tfa.viz import theme


def league_caterpillar(clubs: pd.DataFrame, path: Path, *, highlight: str,
                       season_label: str, matches: int, snapshot: str) -> list[Path]:
    """Booking index with 95% intervals, one row per club, sorted.

    ``clubs`` needs ``booking_index``, ``lo``, ``hi`` and ``survives_bh``, indexed
    by club. Not ``index``: a column of that name collides with the frame's own
    index in ``sort_values``, which fails at runtime rather than at import.
    """
    ordered = clubs.sort_values("booking_index")
    fig, ax = plt.subplots(figsize=(theme.SINGLE_COLUMN + 2.0, 4.8))

    for y, (name, row) in enumerate(ordered.iterrows()):
        separated = bool(row.survives_bh)
        colour = theme.PALETTE[1] if separated else theme.MUTED
        ax.plot([row.lo, row.hi], [y, y], color=colour,
                linewidth=2.4 if separated else 1.4, solid_capstyle="round", zorder=3)
        ax.plot([row["booking_index"]], [y], marker="o",
                markersize=5.5 if separated else 4, color=colour, zorder=4)
        if str(name) == highlight:
            ax.annotate(f"{row['booking_index']:.3f}", xy=(row["booking_index"], y),
                        xytext=(0, -14), textcoords="offset points",
                        ha="center", fontsize=8,
                        color=theme.PALETTE[1], weight="bold")

    ax.axvline(1.0, color=theme.INK, linewidth=1.0, linestyle="--", zorder=2)
    ax.annotate("expected", xy=(1.0, len(ordered) - 0.4), xytext=(4, 0),
                textcoords="offset points", fontsize=8, color=theme.INK)

    ax.set_yticks(range(len(ordered)))
    ax.set_yticklabels([str(n) for n in ordered.index], fontsize=8)
    ax.set_xlabel("Yellow cards observed ÷ yellow cards expected from fouls")
    ax.set_title(f"Every club, {season_label}, with the uncertainty shown")
    ax.set_xlim(left=0)
    theme.grid(ax, axis="x")

    return theme.save(fig, path, theme.Stamp(
        metric="booking index after era and match situation, 95% Poisson interval",
        sample=f"{matches} matches, {len(ordered)} clubs, {season_label}",
        source="football-data.co.uk", snapshot=snapshot,
    ))
