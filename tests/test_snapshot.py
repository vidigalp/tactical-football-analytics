"""Snapshot provenance: round-trip, hashing, and schema-change detection."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from tfa.snapshot import (
    SnapshotWriter,
    load_snapshot,
    read_manifest,
    schema_hash,
    sha256_bytes,
    snapshot_dir,
)


@pytest.fixture
def frame():
    return pd.DataFrame(
        {
            "Div": ["P1", "P1"],
            "HomeTeam": ["Porto", "Benfica"],
            "AwayTeam": ["Braga", "Sporting"],
            "HF": [11, 14],
            "AF": [13, 9],
        }
    )


def test_snapshot_dir_uses_iso_week(tmp_path):
    when = datetime(2026, 8, 29, tzinfo=UTC)  # ISO week 35
    assert snapshot_dir(tmp_path, when).name == "2026-W35"


def test_write_and_read_round_trip(tmp_path, frame):
    writer = SnapshotWriter(tmp_path / "2026-W35")
    entry = writer.add(
        frame=frame,
        raw=b"raw,csv,bytes",
        source="football-data",
        competition="P1",
        season="2526",
        url="https://example.invalid/P1.csv",
    )
    writer.write_manifest()

    entries = read_manifest(tmp_path / "2026-W35")
    assert len(entries) == 1
    assert entries[0] == entry
    assert entries[0].row_count == 2
    assert entries[0].sha256 == sha256_bytes(b"raw,csv,bytes")

    loaded = load_snapshot(tmp_path / "2026-W35")
    pd.testing.assert_frame_equal(loaded, frame)


def test_schema_hash_detects_added_column(frame):
    before = schema_hash(list(frame.columns))
    after = schema_hash([*frame.columns, "Referee"])
    assert before != after


def test_schema_hash_detects_reordering(frame):
    # A reordered header is still an upstream change worth surfacing.
    cols = list(frame.columns)
    assert schema_hash(cols) != schema_hash(list(reversed(cols)))


def test_schema_hash_is_stable(frame):
    assert schema_hash(list(frame.columns)) == schema_hash(list(frame.columns))


def test_sha256_detects_silent_revision():
    # The failure mode this exists to catch: a "final" season quietly rewritten.
    assert sha256_bytes(b"1,2,3") != sha256_bytes(b"1,2,4")


def test_manifest_is_valid_json_and_sorted(tmp_path, frame):
    writer = SnapshotWriter(tmp_path / "w")
    writer.add(
        frame=frame,
        raw=b"x",
        source="football-data",
        competition="E0",
        season="2526",
        url="https://example.invalid/E0.csv",
    )
    path = writer.write_manifest()
    payload = json.loads(path.read_text())
    assert payload["entry_count"] == 1
    assert payload["entries"][0]["competition"] == "E0"


def test_load_empty_snapshot_returns_empty_frame(tmp_path):
    writer = SnapshotWriter(tmp_path / "empty")
    writer.write_manifest()
    assert load_snapshot(tmp_path / "empty").empty
