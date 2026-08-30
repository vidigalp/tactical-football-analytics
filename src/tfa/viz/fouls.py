"""Figures for the foul-context study.

The argument is spatial and the prose cannot carry it: card risk varies threefold
across the pitch, and clubs sit in a tenth of that range.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from tfa.viz import theme

#: Pappalardo normalises the pitch to 0-100 in the attacking direction of the
#: team in possession, so x is distance upfield from the fouling side's own goal.
PITCH_X, PITCH_Y = 100.0, 100.0


def _pitch(ax: plt.Axes) -> None:
    """Markings only, in a grey that never competes with the data."""
    line = {"color": "#9a9a9a", "linewidth": 0.9, "zorder": 4}
    ax.plot([0, 100, 100, 0, 0], [0, 0, 100, 100, 0], **line)
    ax.plot([50, 50], [0, 100], **line)
    for x0, x1, y0, y1 in [(0, 17, 21.1, 78.9), (83, 100, 21.1, 78.9),
                           (0, 5.8, 36.8, 63.2), (94.2, 100, 36.8, 63.2)]:
        ax.plot([x0, x1, x1, x0], [y0, y0, y1, y1], **line)
    # The axis is compressed vertically to give the pitch real proportions, so
    # a data-space circle draws as an ellipse. Stretch the height to compensate.
    ax.add_patch(plt.matplotlib.patches.Ellipse(
        (50, 50), width=2 * 9.15, height=2 * 9.15 * (105 / 68), fill=False, **line))
    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    # Pappalardo normalises both axes to 0-100. Drawing that square renders a
    # pitch as a rectangle it never is, so the aspect is set to a real one.
    ax.set_aspect(68 / 105)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def card_map(fouls: pd.DataFrame, path: Path, snapshot: str, *,
             bins: int = 14, floor: int = 60) -> list[Path]:
    """Probability that a foul is carded, by where on the pitch it happened.

    Cells holding fewer than ``floor`` fouls are left blank rather than drawn
    from a handful of events, because the corners of a pitch are sparse and a
    heat map invites the eye to read them anyway.
    """
    x_edges = np.linspace(0, PITCH_X, bins + 1)
    y_edges = np.linspace(0, PITCH_Y, bins + 1)
    total, _, _ = np.histogram2d(fouls.x, fouls.y, [x_edges, y_edges])
    carded, _, _ = np.histogram2d(fouls[fouls.card != "none"].x,
                                  fouls[fouls.card != "none"].y, [x_edges, y_edges])
    rate = np.where(total >= floor, carded / np.maximum(total, 1), np.nan)

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN + 0.6, 3.9))
    cmap = LinearSegmentedColormap.from_list(
        "risk", ["#f7f7f7", theme.PALETTE[5], theme.PALETTE[0], theme.PALETTE[1]])
    # A single cell in front of goal reaches about 75% and flattens everything
    # else into one shade. Capping at the 97th percentile keeps the gradient
    # legible; the cap is stated on the colour bar so nothing is hidden.
    ceiling = float(np.nanpercentile(rate, 97) * 100)
    mesh = ax.pcolormesh(x_edges, y_edges, rate.T * 100, cmap=cmap,
                         shading="flat", zorder=2, vmin=0, vmax=ceiling)
    _pitch(ax)

    ax.annotate("own goal", xy=(1, -0.5), ha="left", va="top",
                fontsize=7.5, color=theme.MUTED, annotation_clip=False)
    ax.annotate("attacking direction", xy=(99, -0.5), ha="right", va="top",
                fontsize=7.5, color=theme.MUTED, annotation_clip=False)
    ax.set_title("Card risk is about where you foul", fontsize=10.5)

    bar = fig.colorbar(mesh, ax=ax, fraction=0.028, pad=0.02, extend="max")
    bar.set_label(f"carded (%), capped at {ceiling:.0f}")
    bar.outline.set_visible(False)

    return theme.save(fig, path, theme.Stamp(
        metric="Share of fouls followed by a yellow or red card, by pitch location",
        sample=f"{len(fouls):,} fouls; cells with fewer than {floor} fouls left blank",
        source="Pappalardo et al. (2019), CC BY 4.0",
        snapshot=snapshot))


def minute_curve(fouls: pd.DataFrame, path: Path, snapshot: str) -> list[Path]:
    """Card risk against match minute, with the interval on each point."""
    edges = list(range(0, 91, 5)) + [130]
    band = pd.cut(fouls.minute, edges, include_lowest=True)
    grouped = fouls.groupby(band, observed=True).agg(
        n=("card", "size"), carded=("card", lambda s: (s != "none").sum()))
    grouped["rate"] = grouped.carded / grouped.n
    # Wilson interval: the normal approximation misbehaves on the sparse tail.
    z = 1.96
    n, p = grouped.n, grouped.rate
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    mid = [interval.mid for interval in grouped.index]

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 3.6))
    ax.fill_between(mid, (centre - half) * 100, (centre + half) * 100,
                    color=theme.PALETTE[0], alpha=0.18, zorder=2)
    ax.plot(mid, grouped.rate * 100, color=theme.PALETTE[0], linewidth=1.9,
            marker="o", markersize=3.4, zorder=3)
    ax.axvline(45, color=theme.MUTED, linewidth=0.8, linestyle=":", zorder=1)
    ax.annotate("half time", xy=(45.6, ax.get_ylim()[1] * 0.06), fontsize=7.5,
                color=theme.MUTED)
    ax.set_xlabel("Match minute")
    ax.set_ylabel("Chance the foul\nis carded (%)")
    ax.set_title("The same foul is punished four times harder at the end than the start")
    theme.grid(ax, axis="y")

    return theme.save(fig, path, theme.Stamp(
        metric="Share of fouls followed by a card, by match minute, 95% Wilson intervals",
        sample=f"{len(fouls):,} fouls, five-minute bands",
        source="Pappalardo et al. (2019), CC BY 4.0",
        snapshot=snapshot))


def unused_lever(fouls: pd.DataFrame, clubs: pd.DataFrame, path: Path,
                 snapshot: str) -> list[Path]:
    """The gradient runs the length of the pitch; the clubs sit in a tenth of it.

    One axes, with the club positions drawn as a band inside it. An earlier
    two-panel version put the shared x-label underneath the lower panel, where
    it collided with the provenance stamp that every figure here carries.
    """
    edges = np.linspace(0, 100, 21)
    band = pd.cut(fouls.x, edges, include_lowest=True)
    grouped = fouls.groupby(band, observed=True).agg(
        n=("card", "size"), carded=("card", lambda s: (s != "none").sum()))
    grouped = grouped[grouped.n >= 100]
    grouped["rate"] = grouped.carded / grouped.n
    mid = [interval.mid for interval in grouped.index]

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 4.0))
    ax.plot(mid, grouped.rate * 100, color=theme.PALETTE[0], linewidth=2.0,
            marker="o", markersize=3.6, zorder=4)

    lo, hi = clubs.x.min(), clubs.x.max()
    ax.axvspan(lo, hi, color=theme.PALETTE[1], alpha=0.12, zorder=1)

    # The rug sits just above the axis floor, inside the data area.
    top = grouped.rate.max() * 100
    floor = -top * 0.045
    ax.scatter(clubs.x, np.full(len(clubs), floor), s=90, marker="|",
               color=theme.PALETTE[1], linewidth=1.1, zorder=5, clip_on=False)
    ax.set_ylim(floor * 2.1, top * 1.06)

    ax.annotate(
        f"each mark is one club's average foul position\n"
        f"{len(clubs)} clubs, all between {lo:.0f} and {hi:.0f}",
        xy=(hi + 3, floor), va="center", ha="left", fontsize=7.5,
        color=theme.MUTED)
    ax.annotate("a foul here is carded\nabout 38% of the time",
                xy=(2.5, grouped.rate.iloc[0] * 100), xytext=(11, 33),
                fontsize=7.5, color=theme.MUTED,
                arrowprops={"arrowstyle": "->", "color": theme.MUTED,
                            "linewidth": 0.7})

    ax.set_xlabel("Distance upfield from the fouling team's own goal (0 = own goal line)")
    ax.set_ylabel("Chance the foul\nis carded (%)")
    ax.set_title("Every club fouls in the same tenth of the pitch")
    theme.grid(ax, axis="y")

    return theme.save(fig, path, theme.Stamp(
        metric="Card rate by pitch position, against the range clubs actually occupy",
        sample=f"{len(fouls):,} fouls; {len(clubs)} clubs with 200+ fouls",
        source="Pappalardo et al. (2019), CC BY 4.0",
        snapshot=snapshot))


def placement_null(clubs: pd.DataFrame, path: Path, snapshot: str) -> list[Path]:
    """Where a club fouls against how often it is carded. The expected line is absent."""
    from scipy import stats

    r, p = stats.pearsonr(clubs.x, clubs.carded)
    z = np.arctanh(r)
    se = 1 / np.sqrt(len(clubs) - 3)

    fig, ax = plt.subplots(figsize=(theme.SINGLE_COLUMN + 1.9, 3.6))
    ax.scatter(clubs.x, clubs.carded * 100, s=30, color=theme.PALETTE[0],
               alpha=0.75, edgecolor="white", linewidth=0.5, zorder=3)
    fit = np.polyfit(clubs.x, clubs.carded * 100, 1)
    span = np.array([clubs.x.min(), clubs.x.max()])
    ax.plot(span, np.polyval(fit, span), color=theme.PALETTE[1],
            linewidth=1.6, zorder=2)
    ax.set_xlabel("Club's average foul position")
    ax.set_ylabel("Club's card rate\nper foul (%)")
    ax.set_title(f"r = {r:+.2f}   95% CI [{np.tanh(z - 1.96 * se):+.2f}, "
                 f"{np.tanh(z + 1.96 * se):+.2f}]", fontsize=9.5)
    theme.grid(ax, axis="both")

    return theme.save(fig, path, theme.Stamp(
        metric="Club mean foul position against club card rate per foul",
        sample=f"{len(clubs)} clubs with 200+ fouls, five leagues, 2017-18",
        source="Pappalardo et al. (2019), CC BY 4.0",
        snapshot=snapshot))
