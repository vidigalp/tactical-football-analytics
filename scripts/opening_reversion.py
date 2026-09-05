"""What happened to every club that opened a season the way Porto have?

The live page shows one club four matches into a season with an index far below
every other club in its league, and a sealed test that resolves in November. The
question a reader asks next is the obvious one: does an opening like this ever
turn into a season like this?

The archive can answer that without waiting. Every completed team-season in the
snapshot is cut at the same point Porto's season currently stands, its opening
index is computed, the most extreme openings are kept, and the rest of each of
those seasons is read off. Nothing here is fitted or adjusted: the index is
yellows over yellows expected at the league-season's own yellows-per-foul rate, so
the comparison is deliberately cruder than the situation-adjusted figure on the
same page, and it is only used to ask how openings and endings relate.

The follow-up window is the seven matches after the opening. The sealed test
counts matchweeks 4 to 10, which includes the fourth match of the opening itself,
so the two windows overlap by one match and the counts are not directly
comparable. The out-of-sample window is used here because it is the one that
asks a fair question of the comparison clubs.

Run: uv run python scripts/opening_reversion.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest
from tfa.viz import season as season_viz
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]
REPORT = "live-season-portugal"
SEASON_STATUS = ROOT / "reports" / REPORT / "season_status.json"

#: The club the live test is about, and its league in football-data.co.uk codes.
CLUB = "Porto"
LEAGUE = "P1"

#: A team-season counts as completed once it has this many matches. Every league
#: in the snapshot plays at least 30; a season cut short is not a comparison.
COMPLETE = 30

#: The most extreme share of openings kept for the follow-up. A quantile rather
#: than a chosen threshold, so the cut is set by the archive and not by looking
#: at where the club sits.
EXTREME_QUANTILE = 0.01

#: Matches after the opening that the follow-up counts. Seven, the length of the
#: sealed test's window.
FOLLOW_UP = 7

#: The sealed test's reading of a seven-match yellow count.
REAL_AT_MOST = 7
NOISE_AT_LEAST = 12


def load(snapshot: Path) -> pd.DataFrame:
    entries = [e for e in read_manifest(snapshot) if e.source == "football-data"]
    frame = pd.concat(
        [pd.read_parquet(snapshot / e.parquet_path) for e in entries], ignore_index=True
    )
    return frame.dropna(subset=["HF", "AF", "HY", "AY"])


def main() -> None:
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    status = json.loads(SEASON_STATUS.read_text())
    club_now = status["table"][CLUB]
    window = int(club_now["matches"])

    teams = to_team_match(load(snapshot)).sort_values(["Div", "season", "team", "Date"])
    keys = ["Div", "season", "team"]
    teams["n"] = teams.groupby(keys).cumcount() + 1

    # League-season card rate over the whole season, every club. The index is
    # relative to it, so a strict or lenient season does not read as a club.
    rate = teams.groupby(["Div", "season"]).apply(
        lambda g: g.yellows.sum() / g.fouls.sum(), include_groups=False
    ).rename("rate")

    size = teams.groupby(keys).size()
    completed = size[size >= COMPLETE].index
    opening = teams[teams.n <= window].groupby(keys).agg(
        fouls_open=("fouls", "sum"), yellows_open=("yellows", "sum"))
    rest = teams[teams.n > window].groupby(keys).agg(
        fouls_rest=("fouls", "sum"), yellows_rest=("yellows", "sum"))
    follow = teams[(teams.n > window) & (teams.n <= window + FOLLOW_UP)].groupby(keys).agg(
        yellows_follow=("yellows", "sum"), matches_follow=("fouls", "size"))

    table = opening.join(rest, how="inner").join(follow, how="inner")
    table = table[table.index.isin(completed) & (table.matches_follow == FOLLOW_UP)]
    table = table.join(rate, on=["Div", "season"])
    table["index_open"] = table.yellows_open / (table.fouls_open * table.rate)
    table["index_rest"] = table.yellows_rest / (table.fouls_rest * table.rate)
    table["index_season"] = (table.yellows_open + table.yellows_rest) / (
        (table.fouls_open + table.fouls_rest) * table.rate)

    # The club's opening on the same crude scale, at this season's league rate.
    current_rate = float(rate.loc[(LEAGUE, status["season"])])
    club_open = int(club_now["yellows"]) / (int(club_now["fouls"]) * current_rate)

    cut = float(table.index_open.quantile(EXTREME_QUANTILE))
    extreme = table[table.index_open <= cut].sort_values("index_open")
    as_extreme = table[table.index_open <= club_open]
    follow_counts = extreme.yellows_follow.astype(int)

    league = table.loc[LEAGUE]
    club_history = table.xs(CLUB, level="team").loc[LEAGUE].sort_index()
    lowest = table.sort_values("index_season").iloc[0]
    lowest_key = table.sort_values("index_season").index[0]

    facts = {
        "snapshot": snapshot.name,
        "club": CLUB,
        "window": window,
        "follow_up": FOLLOW_UP,
        "complete_threshold": COMPLETE,
        "team_seasons": int(len(table)),
        "leagues": int(table.index.get_level_values("Div").nunique()),
        "club_index_open": round(club_open, 3),
        "club_open_percentile": round(100 * float((table.index_open <= club_open).mean()), 2),
        "openings_at_least_as_extreme": int(len(as_extreme)),
        "extreme_quantile": EXTREME_QUANTILE,
        "extreme_cut": round(cut, 3),
        "extreme_count": int(len(extreme)),
        "extreme_rest_median": round(float(extreme.index_rest.median()), 3),
        "extreme_rest_min": round(float(extreme.index_rest.min()), 3),
        "extreme_rest_below_0_8": int((extreme.index_rest < 0.8).sum()),
        "extreme_rest_below_0_5": int((extreme.index_rest < 0.5).sum()),
        "extreme_season_min": round(float(extreme.index_season.min()), 3),
        "correlation_open_rest": round(
            float(table[["index_open", "index_rest"]].corr().iloc[0, 1]), 3),
        "opening_median": round(float(table.index_open.median()), 3),
        "rest_percentile_1": round(float(table.index_rest.quantile(0.01)), 3),
        "rest_percentile_5": round(float(table.index_rest.quantile(0.05)), 3),
        "lowest_full_season": {
            "league": lowest_key[0], "season": lowest_key[1], "team": lowest_key[2],
            "index": round(float(lowest.index_season), 3),
        },
        "follow_up_yellows": {
            "all_median": float(table.yellows_follow.median()),
            "all_share_real": round(float((table.yellows_follow <= REAL_AT_MOST).mean()), 4),
            "league_median": float(league.yellows_follow.median()),
            "league_share_real": round(float((league.yellows_follow <= REAL_AT_MOST).mean()), 4),
            "extreme_counts": sorted(follow_counts.tolist()),
            "extreme_share_real": round(float((follow_counts <= REAL_AT_MOST).mean()), 3),
            "extreme_share_ambiguous": round(float(
                ((follow_counts > REAL_AT_MOST) & (follow_counts < NOISE_AT_LEAST)).mean()), 3),
            "extreme_share_noise": round(float((follow_counts >= NOISE_AT_LEAST).mean()), 3),
            "extreme_leagues": sorted(set(extreme.index.get_level_values("Div"))),
        },
        "club_history": {
            str(season): {
                "index_open": round(float(row.index_open), 3),
                "index_rest": round(float(row.index_rest), 3),
                "index_season": round(float(row.index_season), 3),
                "yellows_follow": int(row.yellows_follow),
            }
            for season, row in club_history.iterrows()
        },
        "club_history_rest_min": round(float(club_history.index_rest.min()), 3),
        "club_history_rest_max": round(float(club_history.index_rest.max()), 3),
        "club_history_follow_min": int(club_history.yellows_follow.min()),
        "extreme": [
            {
                "league": key[0], "season": key[1], "team": key[2],
                "fouls_open": int(row.fouls_open), "yellows_open": int(row.yellows_open),
                "index_open": round(float(row.index_open), 3),
                "index_rest": round(float(row.index_rest), 3),
                "yellows_follow": int(row.yellows_follow),
            }
            for key, row in extreme.iterrows()
        ],
    }
    out = ROOT / "reports" / REPORT / "openings.json"
    out.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

    theme.apply()
    for path in season_viz.openings_scatter(
        table, extreme, ROOT / "reports" / REPORT / "figures" / "fig2-openings-revert",
        club=CLUB, club_open=club_open, window=window, snapshot=snapshot.name,
    ):
        print(f"wrote {path.relative_to(ROOT)}")

    print(f"{len(table):,} completed team-seasons, opening window {window} matches")
    print(f"{CLUB} opening index {club_open:.3f}; "
          f"{len(as_extreme)} openings at least as extreme")
    print(f"most extreme {100 * EXTREME_QUANTILE:.0f}% of openings: index <= {cut:.3f}, "
          f"{len(extreme)} team-seasons")
    print(f"  rest-of-season index: median {facts['extreme_rest_median']:.2f}, "
          f"min {facts['extreme_rest_min']:.2f}, "
          f"{facts['extreme_rest_below_0_8']} below 0.8")
    print(f"  yellows in next {FOLLOW_UP}: {facts['follow_up_yellows']['extreme_counts']}")
    print(f"lowest full season: {lowest_key} at {lowest.index_season:.3f}")
    print(f"{CLUB} history rest-of-season: "
          f"{facts['club_history_rest_min']:.2f} to {facts['club_history_rest_max']:.2f}")
    print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
