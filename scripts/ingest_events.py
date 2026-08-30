"""Reduce the Pappalardo event logs to a foul-level table.

The only openly licensed source of foul location and timing this project has
found (CC BY 4.0, see DATA_SOURCES.md). Nine hundred megabytes of raw events go
in; one parquet of fouls comes out, small enough to commit so the analysis is
reproducible without the download.

Run: uv run python scripts/ingest_events.py
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "external" / "pappalardo"
OUT = ROOT / "data" / "events"

#: figshare article holding events.zip, from the collection recorded in DATA_SOURCES.md.
EVENTS_ARTICLE = 7770599

LEAGUES = {
    "events_England.json": "England",
    "events_France.json": "France",
    "events_Germany.json": "Germany",
    "events_Italy.json": "Italy",
    "events_Spain.json": "Spain",
}

#: Tag vocabulary, from the collection's own mapping file.
GOAL, COUNTER = 101, 1901
CARDS = {1701: "red", 1702: "yellow", 1703: "second_yellow"}

#: A goal appears twice: once on the scorer's Shot or Free Kick, once on the
#: opposing keeper's Save attempt. Counting both would double every scoreline.
SCORING_EVENTS = {"Shot", "Free Kick"}


def download() -> Path:
    archive = CACHE / "events.zip"
    if archive.exists():
        return archive
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = requests.get(
        f"https://api.figshare.com/v2/articles/{EVENTS_ARTICLE}", timeout=60).json()
    url = meta["files"][0]["download_url"]
    with requests.get(url, stream=True, timeout=900) as response:
        response.raise_for_status()
        with archive.open("wb") as handle:
            for chunk in response.iter_content(1 << 20):
                handle.write(chunk)
    return archive


def minute(event: dict) -> float:
    """Match minute, counting the second half from 45."""
    base = {"1H": 0.0, "2H": 45.0, "E1": 90.0, "E2": 105.0, "P": 120.0}
    return base.get(event["matchPeriod"], 0.0) + event["eventSec"] / 60.0


def fouls_for(events: list[dict], league: str) -> list[dict]:
    """Fouls with the score state at the moment they were committed."""
    goals: dict[int, list[tuple[float, int]]] = {}
    for event in events:
        if event["eventName"] not in SCORING_EVENTS:
            continue
        if any(tag["id"] == GOAL for tag in event["tags"]):
            goals.setdefault(event["matchId"], []).append(
                (minute(event), event["teamId"]))
    for timeline in goals.values():
        timeline.sort()

    rows = []
    for event in events:
        if event["eventName"] != "Foul":
            continue
        positions = event.get("positions") or []
        if not positions:
            continue
        tags = {tag["id"] for tag in event["tags"]}
        when = minute(event)

        scored = conceded = 0
        for goal_minute, team in goals.get(event["matchId"], ()):
            if goal_minute >= when:
                break
            if team == event["teamId"]:
                scored += 1
            else:
                conceded += 1

        rows.append({
            "league": league,
            "match_id": event["matchId"],
            "team_id": event["teamId"],
            "player_id": event["playerId"],
            # Pappalardo normalises the pitch to 0-100 in the attacking
            # direction of the team in possession, so x is distance upfield
            # from the fouling team's own goal.
            "x": float(positions[0]["x"]),
            "y": float(positions[0]["y"]),
            "minute": when,
            "period": event["matchPeriod"],
            "counter_attack": COUNTER in tags,
            "card": next((name for tag, name in CARDS.items() if tag in tags), "none"),
            "score_diff": scored - conceded,
        })
    return rows


def main() -> None:
    archive = download()
    OUT.mkdir(parents=True, exist_ok=True)

    frames = []
    with zipfile.ZipFile(archive) as bundle:
        for filename, league in LEAGUES.items():
            with bundle.open(filename) as handle:
                events = json.load(handle)
            rows = fouls_for(events, league)
            frames.append(pd.DataFrame(rows))
            print(f"  {league:<9} {len(events):>9,} events  ->  {len(rows):>7,} fouls")

    fouls = pd.concat(frames, ignore_index=True)
    path = OUT / "fouls_bigfive_2017-18.parquet"
    fouls.to_parquet(path, index=False)

    carded = (fouls.card != "none").mean()
    print(f"\n{len(fouls):,} fouls, {fouls.match_id.nunique():,} matches, "
          f"{fouls.team_id.nunique()} clubs")
    print(f"carded: {carded:.1%}   counter-attack fouls: {fouls.counter_attack.mean():.1%}")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
