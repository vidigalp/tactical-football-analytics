"""Figures for Week 1: what the free football data can and cannot support."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from tfa.competitions import COMPETITIONS, season_start_year
from tfa.viz import theme

DISCIPLINE = ["HF", "AF", "HY", "AY", "HR", "AR"]
SHOOTING = ["HS", "AS", "HST", "AST", "HC", "AC"]
FOOTBALL_COLUMNS = DISCIPLINE + SHOOTING


def coverage_timeline(audit: pd.DataFrame, path: Path, snapshot: str) -> list[Path]:
    """When each league's fouls-and-cards data actually begins.

    The point of the figure: a file existing is not the same as a file being
    usable, and the gap between those two things is seventeen years wide.
    """
    frame = audit[audit["available"]].copy()
    frame["year"] = frame["season"].map(season_start_year)
    frame["usable"] = frame[DISCIPLINE].all(axis=1)

    order = sorted(
        COMPETITIONS,
        key=lambda c: (COMPETITIONS[c].discipline_from, COMPETITIONS[c].country),
    )

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN + 1.4, 4.2))

    for row, code in enumerate(order):
        sub = frame[frame["competition"] == code]
        present = sub[sub["usable"]]["year"]
        absent = sub[~sub["usable"]]["year"]

        ax.scatter(absent, [row] * len(absent), s=26, marker="s",
                   color="#e8e8e8", edgecolor="#cccccc", linewidth=0.4, zorder=2)
        ax.scatter(present, [row] * len(present), s=26, marker="s",
                   color=theme.PALETTE[0], zorder=3)

        # Season counts sit in a fixed right-hand column rather than beside the
        # first marker, so they never collide with the axis or with each other.
        usable_count = int(sub["usable"].sum())
        ax.annotate(
            f"{COMPETITIONS[code].discipline_from} · {usable_count} seasons",
            xy=(2026.6, row),
            va="center", ha="left",
            fontsize=7.5, color=theme.MUTED,
            annotation_clip=False,
        )

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([COMPETITIONS[c].country for c in order])
    ax.set_xlabel("Season (start year)")
    ax.set_title("Fouls and cards did not arrive at once")
    ax.set_xlim(1999.2, 2026.0)
    ax.set_ylim(len(order) - 0.4, -0.8)
    theme.grid(ax, axis="x")

    handles = [
        plt.Line2D([], [], marker="s", linestyle="", markersize=6,
                   color=theme.PALETTE[0], label="fouls and cards present"),
        plt.Line2D([], [], marker="s", linestyle="", markersize=6,
                   color="#e8e8e8", markeredgecolor="#cccccc",
                   label="file exists, but no match statistics"),
    ]
    # Below the axis: above the plot it collides with the left-aligned title,
    # and inside the plot it covers the sparsest rows.
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.16),
              ncol=2, borderaxespad=0)

    ax.annotate(
        "Germany's series is interrupted",
        xy=(2002, 1), xytext=(2003.4, -0.75),
        fontsize=7.5, color=theme.MUTED,
        arrowprops={"arrowstyle": "->", "color": theme.MUTED, "linewidth": 0.7},
    )

    usable = int(frame["usable"].sum())
    return theme.save(
        fig,
        path,
        theme.Stamp(
            metric="Presence of HF/AF/HY/AY/HR/AR in the season file",
            sample=f"{usable} of {len(frame)} league-seasons usable, 2000-2025",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )


def width_versus_football(audit: pd.DataFrame, path: Path, snapshot: str) -> list[Path]:
    """Total columns against the count that describe the match.

    The files more than doubled in width while the football content stayed flat.
    Almost all of the growth is betting odds.
    """
    frame = audit[audit["available"]].copy()
    frame["year"] = frame["season"].map(season_start_year)
    frame["football"] = frame[FOOTBALL_COLUMNS].sum(axis=1)

    by_year = frame.groupby("year").agg(
        total=("column_count", "median"),
        football=("football", "median"),
    )

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN, 3.8))

    ax.plot(by_year.index, by_year["total"], marker="o", markersize=4,
            color=theme.PALETTE[0], label="all columns")
    ax.plot(by_year.index, by_year["football"], marker="s", markersize=4,
            color=theme.PALETTE[1], label="columns describing the match")
    ax.fill_between(by_year.index, by_year["football"], by_year["total"],
                    color=theme.PALETTE[0], alpha=0.07)

    ax.annotate(
        "the gap is almost entirely betting odds",
        xy=(2022, 70), xytext=(2010, 96),
        fontsize=8, color=theme.MUTED,
        arrowprops={"arrowstyle": "->", "color": theme.MUTED, "linewidth": 0.7},
    )

    ax.set_xlabel("Season (start year)")
    ax.set_ylabel("Median columns per file")
    ax.set_title("The files doubled in width. The football did not.")
    ax.set_ylim(0, None)
    ax.legend(loc="upper left")
    theme.grid(ax)

    return theme.save(
        fig,
        path,
        theme.Stamp(
            metric="Median column count per league-season file",
            sample=f"{len(frame)} league-seasons across 11 divisions, 2000-2025",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )


def referee_coverage(audit: pd.DataFrame, path: Path, snapshot: str) -> list[Path]:
    """Which leagues name the official, and when they stopped.

    The table version of this hides the shape. Two associations published
    referee names and then stopped, which is the opposite of what you expect a
    dataset to do over twenty-six years, and it is the binding constraint on
    every discipline question this project can ask.
    """
    frame = audit[audit["available"]].copy()
    frame["year"] = frame["season"].map(season_start_year)
    frame["named"] = frame["Referee"].fillna(False).astype(bool)

    # Most coverage first, so the two continuous series anchor the top and the
    # seven empty rows read as a block rather than as scattered absences.
    order = sorted(
        frame["competition"].unique(),
        key=lambda c: (-frame[frame["competition"] == c]["named"].sum(),
                       COMPETITIONS[c].country),
    )

    fig, ax = plt.subplots(figsize=(theme.DOUBLE_COLUMN + 1.4, 4.0))

    for row, code in enumerate(order):
        sub = frame[frame["competition"] == code]
        named = sub[sub["named"]]["year"]
        unnamed = sub[~sub["named"]]["year"]

        ax.scatter(unnamed, [row] * len(unnamed), s=26, marker="s",
                   color="#e8e8e8", edgecolor="#cccccc", linewidth=0.4, zorder=2)
        ax.scatter(named, [row] * len(named), s=26, marker="s",
                   color=theme.PALETTE[0], zorder=3)

        count = int(sub["named"].sum())
        label = f"{count} seasons" if count else "never"
        ax.annotate(label, xy=(2026.6, row), va="center", ha="left",
                    fontsize=7.5, color=theme.MUTED, annotation_clip=False)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([COMPETITIONS[c].country for c in order])
    ax.set_xlabel("Season (start year)")
    ax.set_title("Referee names: two leagues have them, two lost them")
    ax.set_xlim(1999.2, 2026.0)
    ax.set_ylim(len(order) - 0.4, -0.8)
    theme.grid(ax, axis="x")

    handles = [
        plt.Line2D([], [], marker="s", linestyle="", markersize=6,
                   color=theme.PALETTE[0], label="referee named"),
        plt.Line2D([], [], marker="s", linestyle="", markersize=6,
                   color="#e8e8e8", markeredgecolor="#cccccc",
                   label="match data present, no referee"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.16),
              ncol=2, borderaxespad=0)

    return theme.save(
        fig, path,
        theme.Stamp(
            metric="Seasons naming the match official, per league",
            sample=f"{len(frame)} league-seasons with match data, 11 divisions",
            source="football-data.co.uk",
            snapshot=snapshot,
        ),
    )
