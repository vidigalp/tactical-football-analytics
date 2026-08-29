"""Render the Week 1 figures from the committed snapshot.

Runs entirely offline: reads the snapshot, writes figures. If this needs the
network, provenance has been broken somewhere.
"""

from __future__ import annotations

import json
from pathlib import Path

from tfa.snapshot import load_snapshot, read_manifest
from tfa.viz import theme, week01

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    theme.apply()

    snapshots = sorted((ROOT / "data" / "snapshots").glob("*-W*"))
    if not snapshots:
        raise SystemExit("no snapshot found — run scripts/run_audit.py first")
    directory = snapshots[-1]

    entries = read_manifest(directory)
    snapshot_label = f"{directory.name} ({entries[0].retrieved_at[:10]})"
    audit = load_snapshot(directory)

    out = ROOT / "reports" / directory.name / "figures"
    written = []
    written += week01.coverage_timeline(audit, out / "coverage-timeline", snapshot_label)
    written += week01.width_versus_football(audit, out / "width-vs-football", snapshot_label)

    for path in written:
        print(f"wrote {path.relative_to(ROOT)}")

    # Facts the report text binds to, so no numeral is typed by hand.
    live = audit[audit["available"]]
    disc = ["HF", "AF", "HY", "AY", "HR", "AR"]
    facts = {
        "snapshot": directory.name,
        "retrieved": entries[0].retrieved_at,
        "league_seasons_probed": int(len(audit)),
        "league_seasons_available": int(len(live)),
        "league_seasons_usable": int(live[disc].all(axis=1).sum()),
        "leagues": int(audit["competition"].nunique()),
    }
    facts_path = ROOT / "reports" / directory.name / "facts.json"
    facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"wrote {facts_path.relative_to(ROOT)}")
    print(json.dumps(facts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
