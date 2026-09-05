"""Did the newest snapshot add anything the one before it did not have?

The weekly job must tell "nothing new" from "I am broken", and it must not
commit a 3.5 MB snapshot that is byte-for-byte the last one. Fewer leagues or
fewer rows than the previous snapshot is a broken fetch and exits non-zero. The
same rows is a quiet week: the new directory is removed so the archive stays
additive rather than repetitive, and ``changed=false`` is written for the
workflow. More rows is new data, ``changed=true``.

Run: uv run python scripts/snapshot_delta.py [--remove-if-unchanged]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]


def rows(snapshot: Path) -> dict[str, int]:
    return {e.competition: e.row_count for e in read_manifest(snapshot)
            if e.source == "football-data"}


def emit(changed: bool) -> None:
    line = f"changed={'true' if changed else 'false'}"
    print(line)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as handle:
            handle.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove-if-unchanged", action="store_true")
    args = parser.parse_args()

    snapshots = sorted((ROOT / "data" / "snapshots").glob("*-W*"))
    if len(snapshots) < 2:
        emit(True)
        return 0
    previous, latest = rows(snapshots[-2]), rows(snapshots[-1])

    missing = sorted(set(previous) - set(latest))
    if missing:
        print(f"{snapshots[-1].name} lost leagues present in {snapshots[-2].name}: {missing}")
        return 1
    shrunk = sorted(c for c in previous if latest[c] < previous[c])
    if shrunk:
        print(f"{snapshots[-1].name} has fewer rows than {snapshots[-2].name} in: {shrunk}")
        return 1

    added = {c: latest[c] - previous.get(c, 0) for c in latest if latest[c] != previous.get(c, 0)}
    for code, n in sorted(added.items()):
        print(f"  {code:<4} +{n} matches")
    if not added:
        print(f"{snapshots[-1].name} adds nothing to {snapshots[-2].name}")
        if args.remove_if_unchanged:
            shutil.rmtree(snapshots[-1])
            print(f"removed {snapshots[-1].relative_to(ROOT)}")
    emit(bool(added))
    return 0


if __name__ == "__main__":
    sys.exit(main())
