"""Build the two-panel replacement figure. Offline, from the committed snapshot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tfa.competitions import season_start_year
from tfa.metrics.discipline import team_season
from tfa.snapshot import read_manifest
from tfa.viz import persistence, theme

ROOT = Path(__file__).resolve().parents[1]

#: The study these figures belong to.
REPORT = "2026-W36"


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    matches["year"] = matches["season"].map(season_start_year)
    completed = matches[matches["year"] <= 2025]

    teams = team_season(completed)
    teams = teams[teams["matches"] >= 30].copy()
    teams["year"] = teams["season"].map(season_start_year)
    teams["ypf"] = teams["yellows"] / teams["fouls"]

    latest = teams[teams["year"] == teams["year"].max()]

    rows = []
    for (_div, _team), g in teams.groupby(["Div", "team"]):
        lookup = {int(r.year): float(r.ypf) for r in g.itertuples()}
        for year, value in lookup.items():
            if year + 1 in lookup:
                rows.append({"this_season": value, "next_season": lookup[year + 1]})
    pairs = pd.DataFrame(rows).dropna()

    theme.apply()
    written = persistence.league_phase_and_persistence(
        latest,
        pairs,
        ROOT / "reports" / directory.name / "figures" / "leagues-and-persistence",
        season_label=f"{int(latest['year'].iloc[0])}-"
                     f"{str(int(latest['year'].iloc[0]) + 1)[-2:]}",
        snapshot=directory.name,
    )
    for p in written:
        print("wrote", p.relative_to(ROOT))
    print(f"\n{len(latest)} teams in latest completed season; "
          f"{len(pairs):,} consecutive club-season pairs")


if __name__ == "__main__":
    main()
