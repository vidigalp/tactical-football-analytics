"""Profile the ingested match data: coverage, quality, and first look.

Read-only. Answers "what do we actually have?" before any modelling.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tfa.competitions import COMPETITIONS, season_start_year
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 200)


def load_matches(directory: Path) -> pd.DataFrame:
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    frames = [pd.read_parquet(directory / e.parquet_path) for e in entries]
    frame = pd.concat(frames, ignore_index=True)
    frame["year"] = frame["season"].map(season_start_year)
    return frame


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    m = load_matches(directory)

    print(f"snapshot {directory.name} — {len(m):,} matches, "
          f"{m['year'].min()}-{m['year'].max()}\n")

    print("=== INTEGRITY ===")
    dupes = m.duplicated(subset=["Div", "season", "Date", "HomeTeam", "AwayTeam"]).sum()
    print(f"duplicate fixtures            : {dupes}")
    print(f"missing dates                 : {m['Date'].isna().sum()}")
    print(f"fouls negative or absurd (>50): {((m.HF > 50) | (m.AF > 50)).sum()}")
    print(f"cards exceed fouls + 6        : {((m.HY > m.HF + 6) | (m.AY > m.AF + 6)).sum()}")
    print(f"shots on target > shots       : {((m.HST > m.HS) | (m.AST > m.AS)).sum()}")

    print("\n=== TEAM NAMING (a stable count means names are consistent) ===")
    rows = []
    for code, g in m.groupby("Div"):
        teams_per_season = g.groupby("season")["HomeTeam"].nunique()
        rows.append({
            "league": code,
            "country": COMPETITIONS[code].country,
            "distinct_teams_all_time": pd.concat([g.HomeTeam, g.AwayTeam]).nunique(),
            "teams_per_season_min": teams_per_season.min(),
            "teams_per_season_max": teams_per_season.max(),
        })
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== COMPLETENESS BY COLUMN (% present) ===")
    cols = ["HF", "AF", "HY", "AY", "HR", "AR", "HS", "AS", "HST", "AST",
            "HC", "AC", "Referee", "strength_diff"]
    comp = (m.groupby("Div")[cols].apply(lambda g: g.notna().mean() * 100).round(1))
    print(comp.to_string())

    print("\n=== ODDS SOURCE USED ===")
    print(m["odds_source"].value_counts(dropna=False).to_string())

    print("\n=== DISCIPLINE BY LEAGUE (all seasons pooled WITHIN league) ===")
    m["fouls"] = m.HF + m.AF
    m["yellows"] = m.HY + m.AY
    m["reds"] = m.HR + m.AR
    disc = m.groupby(["Div"]).agg(
        matches=("fouls", "size"),
        fouls_per_match=("fouls", "mean"),
        yellows_per_match=("yellows", "mean"),
        reds_per_match=("reds", "mean"),
    )
    disc["fouls_per_yellow"] = disc.fouls_per_match / disc.yellows_per_match
    disc["country"] = [COMPETITIONS[c].country for c in disc.index]
    print(disc.round(2).sort_values("fouls_per_yellow", ascending=False).to_string())

    print("\n=== SAME METRIC, BY DECADE — why pooling across eras misleads ===")
    m["era"] = (m.year // 5) * 5
    era = m.groupby("era").agg(
        matches=("fouls", "size"),
        fouls_per_match=("fouls", "mean"),
        yellows_per_match=("yellows", "mean"),
    )
    era["fouls_per_yellow"] = (era.fouls_per_match / era.yellows_per_match).round(2)
    print(era.round(2).to_string())

    print("\n=== ENGLAND: REFEREE COVERAGE (the only long referee series) ===")
    eng = m[m.Div == "E0"]
    print(f"named referees      : {eng['Referee'].nunique()}")
    print(f"matches per referee : median {eng.groupby('Referee').size().median():.0f}, "
          f"max {eng.groupby('Referee').size().max()}")
    top = eng.groupby("Referee").agg(
        matches=("yellows", "size"), yellows_per_match=("yellows", "mean")
    )
    top = top[top.matches >= 100].sort_values("yellows_per_match")
    print(f"\nyellow cards per match, referees with 100+ matches (n={len(top)}):")
    print(f"  lowest : {top.index[0]} {top.iloc[0].yellows_per_match:.2f} "
          f"({int(top.iloc[0].matches)} matches)")
    print(f"  highest: {top.index[-1]} {top.iloc[-1].yellows_per_match:.2f} "
          f"({int(top.iloc[-1].matches)} matches)")
    print(f"  spread : {top.yellows_per_match.max() - top.yellows_per_match.min():.2f} "
          f"cards per match between officials")


if __name__ == "__main__":
    main()
