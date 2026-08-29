"""Run the column-availability audit and write it to a dated snapshot.

    uv run python scripts/run_audit.py --from 1993 --to 2025

The output is the evidence base for the Week 1 report: which claims are even
possible, per league, per season, measured rather than assumed.
"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from tfa.audit import PROBE_COLUMNS, deprecation_report, probe_header, summarise
from tfa.competitions import COMPETITIONS, seasons_range
from tfa.ingest.matchhistory import _session
from tfa.snapshot import SnapshotWriter, snapshot_dir

log = logging.getLogger("audit")

ROOT = Path(__file__).resolve().parents[1]


def run(start: int, end: int, workers: int) -> pd.DataFrame:
    seasons = seasons_range(start, end)
    jobs: list[tuple[str, str]] = []
    gap_rows: list[dict[str, object]] = []

    for code, comp in COMPETITIONS.items():
        for season in seasons:
            if season in comp.season_gaps:
                gap_rows.append(
                    {
                        "competition": code,
                        "country": comp.country,
                        "season": season,
                        "available": False,
                        "column_count": 0,
                        "known_gap": True,
                        **{c: False for c in PROBE_COLUMNS},
                    }
                )
            else:
                jobs.append((code, season))

    session = _session()

    def probe(job: tuple[str, str]) -> dict[str, object]:
        code, season = job
        result = probe_header(code, season, session=session)
        return {
            "competition": code,
            "country": COMPETITIONS[code].country,
            "season": season,
            "available": result.available,
            "column_count": result.column_count,
            "known_gap": False,
            **{c: result.has(c) for c in PROBE_COLUMNS},
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(probe, jobs))

    frame = pd.DataFrame(rows + gap_rows)
    return frame.sort_values(["competition", "season"]).reset_index(drop=True)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", type=int, default=1993)
    parser.add_argument("--to", dest="end", type=int, default=2025)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    frame = run(args.start, args.end, args.workers)

    directory = snapshot_dir(ROOT / "data" / "snapshots")
    writer = SnapshotWriter(directory)
    writer.add(
        frame=frame,
        raw=frame.to_csv(index=False).encode(),
        source="audit",
        competition="ALL",
        season=f"{args.start}-{args.end}",
        url="https://www.football-data.co.uk/mmz4281/",
    )
    writer.write_manifest()

    live = frame[frame["available"]]
    print(f"snapshot: {directory}")
    print(f"probed {len(frame)} competition-seasons, {len(live)} available\n")

    print("=== Referee availability (any season) ===")
    ref = live.groupby("competition")["Referee"].any()
    print(", ".join(sorted(ref[ref].index)) or "none")

    print("\n=== Core bundle present in every available file? ===")
    core = ["HF", "AF", "HY", "AY", "HR", "AR", "HS", "AS", "HST", "AST", "HC", "AC"]
    print({c: bool(live[c].all()) for c in core})

    print("\n=== Still documented, long since dropped ===")
    print(deprecation_report(frame).to_string(index=False))

    print("\n=== Per competition ===")
    cols = ["competition", "country", "seasons_available", "first_year", "last_year",
            "Referee", "HF", "HS", "HC"]
    print(summarise(frame)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
