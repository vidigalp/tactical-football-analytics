"""House chart style.

Encoded once so every figure in the project is consistent and defensible:

* **Vector first.** Figures are saved as PDF with embedded Type 42 fonts, so text
  stays selectable and scalable in a manuscript, plus a PNG for the web.
* **Legible in greyscale.** The palette is colourblind-safe and every series is
  also distinguished by marker or hatch, so nothing depends on hue alone.
* **Uncertainty is not optional.** Helpers for intervals exist precisely so that
  plotting a bare point estimate takes more effort than plotting an honest one.
* **Every figure is stamped** with its metric definition, sample size, source and
  snapshot date. A figure that escapes onto social media without provenance is
  the exact artifact this project was built to argue against.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

#: Okabe-Ito, the standard colourblind-safe qualitative palette.
#: Okabe & Ito (2008), "Color Universal Design".
PALETTE: tuple[str, ...] = (
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
)

#: Redundant encoding, so a figure survives being printed in greyscale.
MARKERS: tuple[str, ...] = ("o", "s", "^", "D", "v", "P", "X", "*")

INK = "#1a1a1a"
MUTED = "#6b6b6b"
GRID = "#d9d9d9"

#: Figure widths in inches, sized to journal columns.
SINGLE_COLUMN = 3.5
DOUBLE_COLUMN = 7.2
SOCIAL = 10.0


def apply() -> None:
    """Install the house style globally."""
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelcolor": INK,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": mpl.cycler(color=list(PALETTE)),
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "xtick.color": INK,
            "ytick.color": INK,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.fontsize": 8.5,
            "legend.frameon": False,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "text.color": INK,
            # Type 42 keeps text as selectable vector rather than outlines.
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


@dataclass(frozen=True)
class Stamp:
    """Mandatory provenance footer.

    Required by ``save``. A figure cannot leave this project without saying what
    it measures, how much data it rests on, where the data came from, and when it
    was taken.
    """

    metric: str
    sample: str
    source: str
    snapshot: str

    def render(self) -> str:
        return (
            f"{self.metric}  ·  {self.sample}\n"
            f"Source: {self.source}  ·  Snapshot: {self.snapshot}"
        )


def save(
    fig: plt.Figure,
    path: Path,
    stamp: Stamp,
    *,
    formats: tuple[str, ...] = ("pdf", "png"),
) -> list[Path]:
    """Stamp a figure and write it in every requested format.

    The stamp is not optional by design — see the module docstring.
    """
    # Reserve room at the foot of the figure before stamping. Placing the
    # stamp below the axes without doing this lets it collide with an x-label
    # or a two-line tick label, which is easy to miss until it is published.
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.text(
        0.0,
        0.012,
        stamp.render(),
        fontsize=7,
        color=MUTED,
        va="bottom",
        ha="left",
        transform=fig.transFigure,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suffix in formats:
        out = path.with_suffix(f".{suffix}")
        fig.savefig(out)
        written.append(out)
    return written


def grid(ax: plt.Axes, axis: str = "y") -> None:
    """Apply the house grid: present, but behind the data and quiet."""
    ax.grid(True, axis=axis, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
