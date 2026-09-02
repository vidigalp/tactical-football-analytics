"""Could a club dodge cards by fouling further upfield? Ceiling on the idea.

Study 03 measures an enormous card-risk gradient by pitch position — 31.4% in a
team's own defensive fifth against 8.9% in the attacking fifth — and finds that
no club among 98 exploits it. The obvious question about the club in study 02 is
whether it is the exception: is its 58-fouls-one-yellow run just fouling in safer
places?

This puts a ceiling on that explanation rather than testing it directly, because
the event data covers the big five leagues and not Portugal. The ceiling is
generous by construction. It takes each league's own position gradient, finds the
club whose actual foul placement is most favourable under it, and asks what that
club's placement buys. Then it applies the largest saving any league offers to
the live Portuguese run.

If the most extreme placement profile in the most favourable of five leagues
cannot account for the anomaly, then placement is not the explanation, and that
conclusion does not depend on measuring the Portuguese league at all.

Run: uv run python scripts/placement_ceiling.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REPORT = "live-season-portugal"
EVENTS = ROOT / "data" / "events" / "fouls_bigfive_2017-18.parquet"
SEASON_STATUS = ROOT / "reports" / REPORT / "season_status.json"

#: Pitch thirds-plus, matching the bands study 03 publishes in chart.json.
BANDS = [0, 20, 35, 50, 65, 80, 100]

#: The club the live test is about.
CLUB = "Porto"


def two_sided_poisson(observed: int, expected: float) -> float:
    if expected <= 0:
        return 1.0
    if observed >= expected:
        tail = stats.poisson.sf(observed - 1, expected)
    else:
        tail = stats.poisson.cdf(observed, expected)
    return float(min(1.0, 2 * tail))


def main() -> None:
    fouls = pd.read_parquet(EVENTS)
    # "none" is a literal string in this column, not a null. Reading it as
    # missing marks every foul as carded and silently produces a 100% card
    # rate; the guard below is that the overall share must reproduce study 03's
    # published base rate.
    fouls["carded"] = fouls["card"].astype(str) != "none"
    base_rate = float(fouls.carded.mean())
    fouls["band"] = pd.cut(fouls.x, BANDS, include_lowest=True)

    leagues = []
    for name, group in fouls.groupby("league"):
        gradient = group.groupby("band", observed=True).carded.mean()
        league_base = float(group.carded.mean())
        mixes = []
        for _, club in group.groupby("team_id"):
            share = club.groupby("band", observed=True).size() / len(club)
            mixes.append(float((share * gradient.reindex(share.index)).sum()))
        mixes = np.asarray(mixes)
        own = float(group[group.x <= 20].carded.mean())
        attacking = float(group[group.x > 80].carded.mean())
        leagues.append({
            "league": str(name),
            "clubs": int(len(mixes)),
            "fouls": int(len(group)),
            "base_rate": league_base,
            "own_fifth": own,
            "attacking_fifth": attacking,
            "gradient_ratio": own / attacking,
            "best_mix": float(mixes.min()),
            "worst_mix": float(mixes.max()),
            "best_saving": 1 - float(mixes.min()) / league_base,
        })

    table = pd.DataFrame(leagues).sort_values("best_saving", ascending=False)
    ceiling = float(table.best_saving.iloc[0])
    most_generous = str(table.league.iloc[0])

    club = json.loads(SEASON_STATUS.read_text())["table"][CLUB]
    expected, observed = float(club["expected"]), int(club["yellows"])
    adjusted = expected * (1 - ceiling)
    shortfall = 1 - observed / expected
    explained = (shortfall - (1 - observed / adjusted)) / shortfall

    facts = {
        "base_rate": base_rate,
        # Pooled across the five leagues, so the two headline rates the report
        # quotes are bound here rather than borrowed from study 03's sidecar.
        # They must agree with it; the script recomputes them from the same
        # foul table.
        "own_fifth": float(fouls[fouls.x <= 20].carded.mean()),
        "attacking_fifth": float(fouls[fouls.x > 80].carded.mean()),
        "bands": BANDS,
        "club": CLUB,
        "ceiling_saving": ceiling,
        "most_generous_league": most_generous,
        "gradient_ratio_min": float(table.gradient_ratio.min()),
        "gradient_ratio_max": float(table.gradient_ratio.max()),
        "leagues": leagues,
        "leagues_with_gradient": int((table.gradient_ratio > 1).sum()),
        "leagues_measured": int(len(table)),
        "expected": expected,
        "expected_under_ceiling": adjusted,
        "index": observed / expected,
        "index_under_ceiling": observed / adjusted,
        "shortfall": shortfall,
        "share_of_shortfall_explained": explained,
        "p": two_sided_poisson(observed, expected),
        "p_under_ceiling": two_sided_poisson(observed, adjusted),
    }
    out = ROOT / "reports" / REPORT / "placement.json"
    out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

    print(table[["league", "clubs", "base_rate", "gradient_ratio", "best_saving"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\noverall card rate {base_rate:.4f} — must match study 03's base rate")
    print(f"gradient present in {facts['leagues_with_gradient']} of "
          f"{facts['leagues_measured']} leagues, ratio "
          f"{facts['gradient_ratio_min']:.1f} to {facts['gradient_ratio_max']:.1f}")
    print(f"\nmost generous ceiling: {most_generous}, {100 * ceiling:.1f}% saving")
    print(f"{CLUB}: expected {expected:.2f} -> {adjusted:.2f}, "
          f"index {facts['index']:.3f} -> {facts['index_under_ceiling']:.3f}")
    print(f"  explains {100 * explained:.1f}% of a "
          f"{100 * shortfall:.0f}% shortfall")
    print(f"  p {facts['p']:.2e} -> {facts['p_under_ceiling']:.2e}")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
