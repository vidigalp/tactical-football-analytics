"""Dated, content-addressed snapshots.

The repo *is* the time series. Every fetch is written to a dated directory with a
manifest recording the source URL, fetch time, row count, column schema hash and
a sha256 of the raw bytes. Three properties follow:

1. Any past report can be re-derived exactly, offline.
2. Silent upstream revisions become visible as a hash change on a season that
   should already be final.
3. A schema change upstream fails loudly instead of quietly altering results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

MANIFEST_NAME = "manifest.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def schema_hash(columns: list[str]) -> str:
    """Stable hash of an ordered column list.

    Used to detect an upstream schema change. Order matters: a reordered header
    is still a change worth surfacing.
    """
    return hashlib.sha256("\x1f".join(columns).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class SnapshotEntry:
    """Provenance record for a single fetched file."""

    source: str
    competition: str
    season: str
    url: str
    retrieved_at: str
    row_count: int
    column_count: int
    sha256: str
    schema_hash: str
    parquet_path: str


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def snapshot_dir(root: Path, when: datetime | None = None) -> Path:
    """Return the ISO-week snapshot directory, e.g. ``data/snapshots/2026-W35``."""
    when = when or datetime.now(UTC)
    year, week, _ = when.isocalendar()
    return root / f"{year}-W{week:02d}"


class SnapshotWriter:
    """Accumulates entries and writes a manifest atomically at the end."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._entries: list[SnapshotEntry] = []

    def add(
        self,
        *,
        frame: pd.DataFrame,
        raw: bytes,
        source: str,
        competition: str,
        season: str,
        url: str,
    ) -> SnapshotEntry:
        name = f"{source}__{competition}__{season}.parquet"
        path = self.directory / name
        frame.to_parquet(path, index=False)

        entry = SnapshotEntry(
            source=source,
            competition=competition,
            season=season,
            url=url,
            retrieved_at=iso_now(),
            row_count=int(len(frame)),
            column_count=int(frame.shape[1]),
            sha256=sha256_bytes(raw),
            schema_hash=schema_hash(list(frame.columns)),
            parquet_path=name,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[SnapshotEntry]:
        return list(self._entries)

    def write_manifest(self) -> Path:
        path = self.directory / MANIFEST_NAME
        payload = {
            "created_at": iso_now(),
            "entry_count": len(self._entries),
            "entries": [asdict(e) for e in self._entries],
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)
        return path


def read_manifest(directory: Path) -> list[SnapshotEntry]:
    payload = json.loads((directory / MANIFEST_NAME).read_text())
    return [SnapshotEntry(**e) for e in payload["entries"]]


def load_snapshot(directory: Path) -> pd.DataFrame:
    """Load every parquet in a snapshot directory into one frame.

    This is the offline path: reports are rendered from here, never from the
    network, so a published report can always be reproduced byte for byte.
    """
    entries = read_manifest(directory)
    frames = [pd.read_parquet(directory / e.parquet_path) for e in entries]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
