"""Manager tenures: a hand-verified dataset, treated as such.

Manager identity is not in football-data.co.uk. It has to be assembled by hand,
which makes it the least trustworthy data in this project and the most in need
of explicit handling. Three rules follow:

1. **Every row cites a source.** A tenure without a resolvable URL is not
   admissible. This is the same standard the bibliography is held to, for the
   same reason.
2. **Coverage is measured, never assumed.** :func:`coverage` reports what
   fraction of each club-season is actually attributable to a named manager.
   Analysis is restricted to covered spans rather than quietly treating gaps as
   continuity.
3. **Date precision is recorded.** Many appointments are verifiable only to the
   month. A tenure boundary known to ±15 days cannot support a claim about the
   match immediately after it, and the precision field is what lets a downstream
   model refuse that claim.

The dataset lives in ``data/managers/primeira_liga.csv`` so it is diffable in
review, where a wrong date is far more likely to be spotted than inside a binary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "managers"

#: How precisely a boundary date is known. A model must not attribute a match to
#: a manager when the boundary is less precise than the gap to that match.
PRECISIONS: tuple[str, ...] = ("day", "month", "season")

CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")

COLUMNS: tuple[str, ...] = (
    "club",            # short form as used in the match data
    "club_full",       # full club name, for humans
    "manager",
    "start_date",
    "start_precision",
    "end_date",        # empty string means still in post
    "end_precision",
    "caretaker",
    "source_url",
    "confidence",
    "notes",
)


class TenureError(ValueError):
    """A tenure record violates the dataset's rules. Deliberately fatal."""


@dataclass(frozen=True)
class Tenure:
    club: str
    manager: str
    start: pd.Timestamp
    end: pd.Timestamp | None
    caretaker: bool
    source_url: str
    confidence: str
    start_precision: str = "day"
    end_precision: str = "day"

    def covers(self, when: pd.Timestamp) -> bool:
        if when < self.start:
            return False
        return self.end is None or when <= self.end


def path_for(league: str = "primeira_liga") -> Path:
    return DATA_DIR / f"{league}.csv"


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNS})


def load(league: str = "primeira_liga") -> pd.DataFrame:
    """Load and validate a tenure table."""
    path = path_for(league)
    if not path.exists():
        return empty_frame()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate(frame)
    return frame


def _parse_date(value: str, precision: str) -> pd.Timestamp | None:
    if not value or value.lower() in {"ongoing", "present", ""}:
        return None
    if precision == "season":
        # A season-precision boundary is pinned to 1 July, the conventional
        # start of the European football year.
        return pd.Timestamp(f"{value[:4]}-07-01")
    if precision == "month":
        return pd.Timestamp(f"{value[:7]}-01")
    return pd.Timestamp(value)


def validate(frame: pd.DataFrame) -> None:
    """Reject a table that could produce a wrong attribution.

    Overlapping tenures at one club are the important case: they would let a
    match be credited to two managers, and the resulting double count would be
    invisible in any downstream aggregate.
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise TenureError(f"missing columns: {missing}")

    for i, row in frame.iterrows():
        if not str(row["source_url"]).startswith("http"):
            raise TenureError(f"row {i} ({row['club']}, {row['manager']}): no source URL")
        if row["start_precision"] not in PRECISIONS:
            raise TenureError(f"row {i}: bad start_precision {row['start_precision']!r}")
        if row["end_precision"] not in (*PRECISIONS, ""):
            raise TenureError(f"row {i}: bad end_precision {row['end_precision']!r}")
        if row["confidence"] not in CONFIDENCE:
            raise TenureError(f"row {i}: bad confidence {row['confidence']!r}")

    parsed = to_tenures(frame)
    by_club: dict[str, list[Tenure]] = {}
    for tenure in parsed:
        by_club.setdefault(tenure.club, []).append(tenure)

    for club, tenures in by_club.items():
        tenures.sort(key=lambda t: t.start)
        for earlier, later in zip(tenures, tenures[1:], strict=False):
            if earlier.end is None:
                raise TenureError(
                    f"{club}: {earlier.manager} is marked ongoing but "
                    f"{later.manager} starts afterwards"
                )
            if earlier.end > later.start:
                raise TenureError(
                    f"{club}: {earlier.manager} (to {earlier.end.date()}) overlaps "
                    f"{later.manager} (from {later.start.date()})"
                )


def to_tenures(frame: pd.DataFrame) -> list[Tenure]:
    out = []
    for _, row in frame.iterrows():
        out.append(
            Tenure(
                club=row["club"],
                manager=row["manager"],
                start=_parse_date(row["start_date"], row["start_precision"]),
                end=_parse_date(row["end_date"], row["end_precision"] or "day"),
                caretaker=str(row["caretaker"]).lower() in {"true", "1", "yes"},
                source_url=row["source_url"],
                confidence=row["confidence"],
                start_precision=row["start_precision"],
                end_precision=row["end_precision"] or "day",
            )
        )
    return out


def attach(matches: pd.DataFrame, tenures: pd.DataFrame) -> pd.DataFrame:
    """Label each team-match with its manager, where one is known.

    Adds ``manager`` (NA when uncovered) and ``manager_match_index``, the count
    of matches that manager has taken at that club — which is what makes a
    before-and-after comparison around a change possible.
    """
    parsed = to_tenures(tenures)
    by_club: dict[str, list[Tenure]] = {}
    for tenure in parsed:
        by_club.setdefault(tenure.club, []).append(tenure)

    def lookup(club: str, when: pd.Timestamp) -> str | None:
        for tenure in by_club.get(club, []):
            if tenure.covers(when):
                return tenure.manager
        return None

    out = matches.copy()
    out["manager"] = pd.array(
        [lookup(club, when) for club, when in zip(out["team"], out["Date"], strict=True)],
        dtype="string",
    )
    out = out.sort_values(["team", "Date"])
    # Nullable integer: an uncovered match has no index, and a float column
    # would quietly turn that absence into NaN arithmetic downstream.
    index = out.groupby(["team", "manager"], dropna=True).cumcount() + 1
    out["manager_match_index"] = index.where(out["manager"].notna()).astype("Int64")
    return out


def coverage(matches: pd.DataFrame, tenures: pd.DataFrame) -> pd.DataFrame:
    """What fraction of each club-season has a named manager.

    Published alongside any manager-based result. A finding drawn from 40%
    coverage is a different claim from one drawn from 95%, and the reader is
    entitled to know which.
    """
    labelled = attach(matches, tenures)
    grouped = labelled.groupby(["Div", "season", "team"], as_index=False).agg(
        matches=("manager", "size"),
        covered=("manager", lambda s: int(s.notna().sum())),
    )
    grouped["coverage"] = (grouped["covered"] / grouped["matches"]).round(3)
    return grouped.sort_values(["season", "team"])
