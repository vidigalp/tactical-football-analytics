"""Build the phase-space figures for a league-season.

    uv run python scripts/build_phase.py --league P1 --season 2627

Offline: reads the committed snapshot only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from tfa.competitions import COMPETITIONS, season_start_year
from tfa.metrics.discipline import team_season, with_shrinkage
from tfa.snapshot import read_manifest
from tfa.viz import phase, theme

ROOT = Path(__file__).resolve().parents[1]


def season_label(code: str) -> str:
    start = season_start_year(code)
    return f"{start}-{str(start + 1)[-2:]}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default="P1")
    parser.add_argument("--season", default="2627")
    args = parser.parse_args()

    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [
        e for e in read_manifest(directory)
        if e.source == "football-data" and e.competition == args.league
    ]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    matches = matches[matches["season"] == args.season]
    if matches.empty:
        raise SystemExit(f"no matches for {args.league} {args.season}")

    teams = with_shrinkage(team_season(matches))
    theme.apply()

    comp = COMPETITIONS[args.league]
    label = season_label(args.season)
    out = ROOT / "reports" / directory.name / "figures"
    stamp = f"{directory.name}"

    written = phase.phase_space(
        teams, out / f"phase-{args.league}-{args.season}",
        league=f"{comp.name} ({comp.country})", season_label=label, snapshot=stamp,
    )
    written += phase.raw_versus_shrunk(
        teams, out / f"shrinkage-{args.league}-{args.season}",
        league=f"{comp.name} ({comp.country})", season_label=label, snapshot=stamp,
    )
    for p in written:
        print("wrote", p.relative_to(ROOT))

    cols = ["team", "matches", "fouls", "yellows",
            "fouls_per_card", "fouls_per_card_shrunk",
            "fouls_per_card_lo", "fouls_per_card_hi",
            "cards_per_foul_reliability"]
    view = teams[cols].sort_values("fouls_per_card", ascending=False)
    print(f"\n{comp.name} {label} — {len(teams)} teams, "
          f"median {int(teams.matches.median())} matches\n")
    print(view.round(2).to_string(index=False))
    print(f"\nraw spread    : {view.fouls_per_card.min():.1f} to "
          f"{view.fouls_per_card.max():.1f}")
    print(f"shrunk spread : {view.fouls_per_card_shrunk.min():.1f} to "
          f"{view.fouls_per_card_shrunk.max():.1f}")
    print(f"reliability   : {view.cards_per_foul_reliability.median():.2f} "
          f"(need 0.70 to rank teams — see METHODS.md)")


if __name__ == "__main__":
    main()
