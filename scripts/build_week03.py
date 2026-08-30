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
    for key, value in facts.items():
        print(f"  {key:<22}{value:.4f}" if isinstance(value, float) else f"  {key:<22}{value}")


if __name__ == "__main__":
    main()
