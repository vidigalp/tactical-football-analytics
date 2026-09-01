"""Figures and facts for study 03: is card risk something a club can manage?

Reads the committed foul table, so it runs offline and does not need the 950 MB
event extract.

Run: uv run python scripts/build_week03.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.viz import fouls as viz
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]
REPORT = "2026-W37"
MIN_FOULS = 200


def main() -> None:
    theme.apply()
    path = ROOT / "data" / "events" / "fouls_bigfive_2017-18.parquet"
    fouls = pd.read_parquet(path)
    fouls["carded"] = (fouls.card != "none").astype(int)
    fouls["lat"] = (fouls.y - 50).abs()

    clubs = fouls.groupby(["league", "team_id"]).agg(
        n=("carded", "size"), x=("x", "mean"), lat=("lat", "mean"),
        minute=("minute", "mean"), carded=("carded", "mean")).reset_index()
    clubs = clubs[clubs.n >= MIN_FOULS]

    out = ROOT / "reports" / REPORT / "figures"
    out.mkdir(parents=True, exist_ok=True)
    written = []
    written += viz.card_map(fouls, out / "fig1-card-map", "2026-W37")
    written += viz.minute_curve(fouls, out / "fig2-minute", "2026-W37")
    written += viz.unused_lever(fouls, clubs, out / "fig3-unused-lever", "2026-W37")
    written += viz.placement_null(clubs, out / "fig4-placement-null", "2026-W37")
    for item in written:
        print(f"wrote {item.relative_to(ROOT)}")

    def rate(frame: pd.DataFrame) -> float:
        return float(frame.carded.mean())

    r, p = stats.pearsonr(clubs.x, clubs.carded)
    z, se = np.arctanh(r), 1 / np.sqrt(len(clubs) - 3)

    # How much of the between-club variation in where a club fouls is real
    # rather than the sampling error of a club mean?
    def reliability(column: str) -> float:
        within = fouls.groupby(["league", "team_id"])[column].var()
        size = fouls.groupby(["league", "team_id"])[column].size()
        keep = size >= MIN_FOULS
        sampling = float((within[keep] / size[keep]).mean())
        observed = float(clubs[column].var())
        return max(observed - sampling, 0) / observed

    facts = {
        "fouls": int(len(fouls)),
        "matches": int(fouls.match_id.nunique()),
        "clubs": int(len(clubs)),
        "base_rate": rate(fouls),
        "own_fifth": rate(fouls[fouls.x <= 20]),
        "attacking_fifth": rate(fouls[fouls.x > 80]),
        "first_quarter_hour": rate(fouls[fouls.minute <= 15]),
        "after_ninety": rate(fouls[fouls.minute > 90]),
        "central": rate(fouls[fouls.lat <= 10]),
        "wide": rate(fouls[fouls.lat > 40]),
        "club_x_min": float(clubs.x.min()),
        "club_x_max": float(clubs.x.max()),
        "r_placement": r,
        "r_placement_lo": float(np.tanh(z - 1.96 * se)),
        "r_placement_hi": float(np.tanh(z + 1.96 * se)),
        "r_placement_p": p,
        "reliability_x": reliability("x"),
        "reliability_minute": reliability("minute"),
    }
    (ROOT / "reports" / REPORT / "facts.json").write_text(
        json.dumps(facts, indent=2, sort_keys=True) + "\n")

    # Series for the interactive chart on the site. Emitted here rather than
    # computed in the browser so the figure and the chart cannot disagree.
    def series(column: str, edges: list[float], labels: list[str]) -> list[dict]:
        binned = pd.cut(fouls[column], edges, labels=labels, include_lowest=True)
        grouped = fouls.groupby(binned, observed=True).agg(
            fouls=("carded", "size"), carded=("carded", "sum"))
        rows = []
        for label, row in grouped.iterrows():
            n, k = int(row.fouls), int(row.carded)
            rate = k / n
            # Wilson bounds: the tails are sparse and a normal interval there
            # can run below zero.
            z, centre = 1.96, (k / n + 1.96 ** 2 / (2 * n)) / (1 + 1.96 ** 2 / n)
            half = z * np.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            rows.append({"band": str(label), "fouls": n,
                         "rate": round(100 * rate, 2),
                         "lo": round(100 * max(centre - half, 0), 2),
                         "hi": round(100 * min(centre + half, 1), 2)})
        return rows

    chart = {
        "position": series("x", [0, 20, 35, 50, 65, 80, 100],
                           ["0-20", "20-35", "35-50", "50-65", "65-80", "80-100"]),
        "minute": series("minute", [0, 15, 30, 45, 60, 75, 90, 130],
                         ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90", "90+"]),
        "lateral": series("lat", [0, 10, 20, 30, 40, 50],
                          ["0-10", "10-20", "20-30", "30-40", "40-50"]),
        "baseRate": round(100 * float(fouls.carded.mean()), 2),
        "totalFouls": int(len(fouls)),
    }
    (ROOT / "reports" / REPORT / "chart.json").write_text(
        json.dumps(chart, indent=2) + "\n")
    for key, value in facts.items():
        print(f"  {key:<22}{value:.4f}" if isinstance(value, float) else f"  {key:<22}{value}")


if __name__ == "__main__":
    main()
