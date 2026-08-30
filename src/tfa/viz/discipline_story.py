"""Paper-grade figures for the discipline analysis.

Four panels, in the order the argument runs:

1. Match situation moves booking rate by 32%, league-wide, with no club identity
   involved. This is the largest effect in the analysis and the one that has to
   be removed before any club comparison means anything.
2. Removing it dissolves most club differences. Porto moves from apparently
   lenient to unremarkable; one club survives, in the opposite direction.
3. The effect does not travel with managers who changed clubs.
4. Shrinkage is not a stylistic choice — it demonstrably predicts better out of
   sample, which is the only defence that counts.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tfa.viz import theme

HIGHLIGHT = {"Porto": theme.PALETTE[1], "Sp Lisbon": theme.PALETTE[3]}
NICE = {"Porto": "Porto", "Sp Lisbon": "Sporting", "Benfica": "Benfica",
        "Sp Braga": "Braga"}


def context_effect(bands: pd.DataFrame, path: Path, *, snapshot: str) -> list[Path]:
    """Booking index by pre-match strength band, league-wide.

    ``bands`` needs band, n, multiplier, lo, hi in weakest-to-strongest order.
    """
    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 3.9))

    x = np.arange(len(bands))
    ax.axhline(1.0, color=theme.MUTED, linewidth=0.9, linestyle="--", zorder=1)
    ax.errorbar(
        x, bands["multiplier"],
        yerr=[bands["multiplier"] - bands["lo"], bands["hi"] - bands["multiplier"]],
        fmt="o", markersize=7, color=theme.PALETTE[0], ecolor=theme.PALETTE[0],
        elinewidth=1.4, capsize=0, zorder=3,
    )

    for xi, row in zip(x, bands.itertuples(), strict=True):
        ax.annotate(f"{row.multiplier:.3f}", xy=(xi, row.multiplier),
                    xytext=(0, 11), textcoords="offset points",
                    ha="center", fontsize=8, color=theme.INK)

    swing = 100 * (bands["multiplier"].iloc[0] / bands["multiplier"].iloc[-1] - 1)
    ax.annotate(
        f"{swing:.0f}% swing, and not one club is involved",
        xy=(0.5, 0.08), xycoords="axes fraction", ha="center",
        fontsize=8.5, color=theme.PALETTE[1],
    )

    ax.set_xticks(x)
    ax.set_xticklabels(bands["band"], fontsize=8.5)
    ax.set_ylabel("Yellows received ÷ yellows expected")
    ax.set_xlabel("Pre-match position, from the betting odds")
    ax.set_title("Being the better side is worth a third of a booking rate")
    theme.grid(ax)

    return theme.save(fig, path, theme.Stamp(
        metric="Booking index by strength band, all clubs pooled. 95% Poisson intervals",
        sample=f"{int(bands['n'].sum()):,} team-matches, Primeira Liga 2017-2026",
        source="football-data.co.uk", snapshot=snapshot,
    ))


def clubs_before_after(clubs: pd.DataFrame, path: Path, *, snapshot: str) -> list[Path]:
    """Each club's booking index before and after adjusting for context.

    ``clubs`` needs team, raw, adjusted, lo, hi.
    """
    d = clubs.sort_values("adjusted").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 5.2))

    y = np.arange(len(d))
    ax.axvline(1.0, color=theme.MUTED, linewidth=0.9, linestyle="--", zorder=1)

    for yi, row in zip(y, d.itertuples(), strict=True):
        colour = HIGHLIGHT.get(row.team, theme.PALETTE[0])
        alpha = 1.0 if row.team in HIGHLIGHT else 0.45
        ax.plot([row.raw, row.adjusted], [yi, yi], color=colour,
                alpha=alpha * 0.6, linewidth=1.1, zorder=2)
        ax.plot(row.raw, yi, marker="o", markersize=4.5, color=colour,
                alpha=alpha * 0.55, markerfacecolor="white", zorder=3)
        ax.plot(row.adjusted, yi, marker="s", markersize=5, color=colour,
                alpha=alpha, zorder=4)
        ax.plot([row.lo, row.hi], [yi, yi], color=colour, alpha=alpha * 0.5,
                linewidth=2.6, solid_capstyle="butt", zorder=1)

    ax.set_yticks(y)
    ax.set_yticklabels([NICE.get(t, t) for t in d["team"]], fontsize=8)
    for tick, team in zip(ax.get_yticklabels(), d["team"], strict=True):
        if team in HIGHLIGHT:
            tick.set_color(HIGHLIGHT[team])
            tick.set_fontweight("bold")

    ax.set_xlabel("Booking index   (1.0 = booked exactly as the situation predicts)")
    ax.set_title("Adjust for the situation, and almost every club is ordinary",
                 pad=14)
    theme.grid(ax, axis="x")

    handles = [
        plt.Line2D([], [], marker="o", linestyle="", markersize=6,
                   markerfacecolor="white", color=theme.MUTED, label="raw"),
        plt.Line2D([], [], marker="s", linestyle="", markersize=6,
                   color=theme.MUTED, label="adjusted for era and situation"),
    ]
    # Lower right is the only reliably empty region: the weakly-booked clubs at
    # the foot of the chart do not extend past about 1.05.
    ax.legend(handles=handles, loc="lower right", borderaxespad=0.8)

    porto = d[d.team == "Porto"].iloc[0]
    ax.annotate(
        f"Porto: {porto.raw:.2f} to {porto.adjusted:.2f}\nno longer distinguishable",
        xy=(porto.adjusted, float(d.index[d.team == "Porto"][0])),
        xytext=(22, -30), textcoords="offset points", fontsize=7.5,
        color=HIGHLIGHT["Porto"],
        arrowprops={"arrowstyle": "->", "color": HIGHLIGHT["Porto"], "linewidth": 0.7},
    )
    sporting = d[d.team == "Sp Lisbon"].iloc[0]
    ax.annotate(
        "Sporting: the one club still\nseparated — and booked MORE",
        xy=(sporting.adjusted, float(d.index[d.team == "Sp Lisbon"][0])),
        xytext=(-138, 34), textcoords="offset points", fontsize=7.5,
        color=HIGHLIGHT["Sp Lisbon"],
        arrowprops={"arrowstyle": "->", "color": HIGHLIGHT["Sp Lisbon"],
                    "linewidth": 0.7},
    )

    return theme.save(fig, path, theme.Stamp(
        metric="Booking index per club; bars are 95% Poisson intervals on the adjusted value",
        sample=f"{len(d)} clubs with 80+ matches, Primeira Liga 2017-2026",
        source="football-data.co.uk", snapshot=snapshot,
    ))


def manager_travel(pairs: pd.DataFrame, null_r: np.ndarray, observed_r: float,
                   path: Path, *, snapshot: str) -> list[Path]:
    """Do a manager's spells at two clubs agree? ``pairs`` needs a, b, manager."""
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(theme.DOUBLE_COLUMN + 1.0, 4.2),
        gridspec_kw={"width_ratios": [2.0, 1.05]},
    )

    ax.axhline(1.0, color=theme.MUTED, linewidth=0.7, linestyle=":", zorder=1)
    ax.axvline(1.0, color=theme.MUTED, linewidth=0.7, linestyle=":", zorder=1)
    ax.scatter(pairs["a"], pairs["b"], s=34, color=theme.PALETTE[0],
               alpha=0.75, zorder=3)

    lim = (0.72, 1.28)
    ax.plot(lim, lim, color=theme.MUTED, linestyle="--", linewidth=0.8, zorder=2)
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("Effect at one club")
    ax.set_ylabel("Same manager, another club")
    ax.set_title("(A) A manager's two spells do not agree")
    theme.grid(ax, axis="both")
    ax.annotate(
        f"r = {observed_r:+.2f}\nif the effect were the manager's,\nthese would sit on the line",
        xy=(0.04, 0.84), xycoords="axes fraction", fontsize=8, color=theme.INK,
    )

    ax2.hist(null_r, bins=40, color=theme.PALETTE[0], alpha=0.35,
             edgecolor="none", zorder=2)
    ax2.axvline(observed_r, color=theme.PALETTE[1], linewidth=1.8, zorder=4)
    ax2.annotate("observed", xy=(observed_r, ax2.get_ylim()[1] * 0.86),
                 xytext=(8, 0), textcoords="offset points",
                 fontsize=8, color=theme.PALETTE[1])
    ax2.set_xlabel("Correlation under random pairing")
    ax2.set_ylabel("Shuffles")
    ax2.set_title("(B) Chance does this")
    theme.grid(ax2)

    fig.tight_layout()
    return theme.save(fig, path, theme.Stamp(
        metric=(
            "Spell effect vs its club's baseline excluding that manager; "
            "5,000 permutations"
        ),
        sample=f"{len(pairs)} spell pairs from managers at 2+ clubs, 15+ matches each",
        source="football-data.co.uk", snapshot=snapshot,
    ))


def shrinkage_validation(scores: dict[str, float], path: Path, *,
                         n_pairs: int, snapshot: str) -> list[Path]:
    """Out-of-sample error by method. ``scores`` maps label to RMSE."""
    fig, ax = plt.subplots(figsize=(theme.SINGLE_COLUMN + 2.4, 3.4))

    labels = list(scores)
    values = [scores[k] for k in labels]
    colours = [theme.PALETTE[1], theme.PALETTE[0], theme.MUTED]

    bars = ax.barh(range(len(labels)), values, color=colours, height=0.55, zorder=3)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()

    for bar, value in zip(bars, values, strict=True):
        ax.annotate(f"{value:.5f}", xy=(value, bar.get_y() + bar.get_height() / 2),
                    xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=theme.INK)

    ax.set_xlabel("Error predicting the club's next season (lower is better)")
    ax.set_title("Shrinking beats not shrinking, out of sample")
    ax.set_xlim(0, max(values) * 1.22)
    theme.grid(ax, axis="x")

    gain = 100 * (scores["raw ratio"] - scores["shrunken estimate"]) / scores["raw ratio"]
    ax.annotate(
        f"{gain:.0f}% lower error — and the raw ratio is beaten\n"
        "even by ignoring the club entirely",
        xy=(0.30, 0.12), xycoords="axes fraction", fontsize=8,
        color=theme.PALETTE[1],
    )

    return theme.save(fig, path, theme.Stamp(
        metric="RMSE predicting next season's yellows-per-foul from this season",
        sample=f"{n_pairs:,} consecutive club-season pairs, 11 leagues",
        source="football-data.co.uk", snapshot=snapshot,
    ))
