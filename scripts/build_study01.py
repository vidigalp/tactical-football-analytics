"""Render study 01's figures from the committed snapshot.

Runs entirely offline: reads the snapshot, writes figures. If this needs the
network, provenance has been broken somewhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tfa.snapshot import read_manifest
from tfa.viz import theme, week01

ROOT = Path(__file__).resolve().parents[1]

#: The study these outputs belong to. Deliberately NOT the snapshot name: this
#: script used to derive the directory from the latest snapshot, so when a
#: second snapshot landed it began writing study 01's figures and facts into a
#: directory named after that snapshot. Report identity and data vintage are
#: different things and no longer share a naming scheme.
REPORT = "01-free-football-data"


def main() -> None:
    theme.apply()

    # The most recent snapshot that actually holds an audit, not simply the most
    # recent snapshot. This study is an audit of what the source publishes, and
    # only run_audit.py writes that frame; the match snapshots taken since do
    # not contain one. Taking snapshots[-1] unconditionally made the reproduce
    # path in the README exit non-zero the moment a second snapshot landed.
    snapshots = sorted((ROOT / "data" / "snapshots").glob("*-W*"))
    audited = [d for d in snapshots if any(d.glob("audit__*.parquet"))]
    if not audited:
        raise SystemExit(
            "no snapshot contains an audit frame — run scripts/run_audit.py first"
        )
    directory = audited[-1]

    entries = read_manifest(directory)
    snapshot_label = f"{directory.name} ({entries[0].retrieved_at[:10]})"

    # Not load_snapshot: it concatenates every parquet in the directory, and
    # the match files landed in this snapshot after week 1 was published. That
    # silently turned the audit frame into 58,171 match rows and broke this
    # script's reproduce path without anything failing loudly.
    audit_files = sorted(directory.glob("audit__*.parquet"))
    audit = pd.concat([pd.read_parquet(f) for f in audit_files], ignore_index=True)

    out = ROOT / "reports" / REPORT / "figures"
    written = []
    written += week01.coverage_timeline(audit, out / "coverage-timeline", snapshot_label)
    written += week01.width_versus_football(audit, out / "width-vs-football", snapshot_label)
    written += week01.referee_coverage(audit, out / "referee-coverage", snapshot_label)

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
    facts_path = ROOT / "reports" / REPORT / "facts.json"
    facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"wrote {facts_path.relative_to(ROOT)}")
    print(json.dumps(facts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
