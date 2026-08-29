"""Fetch every usable league-season and write a committed snapshot.

    uv run python scripts/ingest_matches.py

Only seasons that actually carry fouls and cards are fetched — see
tfa.competitions.usable_seasons and the Week 1 audit for why that is 179 of 286.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from tfa.competitions import COMPETITIONS, usable_seasons
from tfa.ingest.matches import prepare
from tfa.ingest.matchhistory import _session, fetch_csv
from tfa.snapshot import SnapshotWriter, snapshot_dir

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("ingest")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", dest="end", type=int, default=2025)
    parser.add_argument("--leagues", nargs="*", default=sorted(COMPETITIONS))
    args = parser.parse_args()

    directory = snapshot_dir(ROOT / "data" / "snapshots")
    writer = SnapshotWriter(directory)
    session = _session()

    totals: list[dict[str, object]] = []

    for code in args.leagues:
        comp = COMPETITIONS[code]
        seasons = usable_seasons(code, args.end)
        frames, raws = [], []

        for season in seasons:
            try:
                fetched = fetch_csv(comp, season, session=session)
            except Exception as exc:  # noqa: BLE001 - recorded, not fatal
                log.warning("  %s %s FAILED: %s", code, season, exc)
                continue
            frames.append(prepare(fetched.frame))
            raws.append(fetched.raw)

        if not frames:
            log.warning("%s: nothing ingested", code)
            continue

        combined = pd.concat(frames, ignore_index=True)
        writer.add(
            frame=combined,
            raw=b"".join(raws),
            source="football-data",
            competition=code,
            season=f"{seasons[0]}-{seasons[-1]}",
            url=comp.url("{season}"),
        )
        totals.append(
            {
                "league": code,
                "country": comp.country,
                "seasons": len(frames),
                "matches": len(combined),
                "with_referee": int(combined["Referee"].notna().sum()),
                "with_odds": int(combined["strength_diff"].notna().sum()),
            }
        )
        log.info("%-4s %-12s %2d seasons  %5d matches", code, comp.country,
                 len(frames), len(combined))

    writer.write_manifest()
    summary = pd.DataFrame(totals)
    print(f"\nsnapshot: {directory}")
    print(summary.to_string(index=False))
    print(f"\nTOTAL {summary['matches'].sum():,} matches "
          f"across {summary['seasons'].sum()} league-seasons")


if __name__ == "__main__":
    main()
