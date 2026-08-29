"""Column-availability audit across competitions and seasons.

This is the evidence base for Week 1. The question it answers — *which claims
are even possible from the free football data that still exists?* — is not
answerable from documentation, because football-data.co.uk's own ``notes.txt``
advertises columns that no live file contains.

So we measure it, commit the measurement, and cite our own snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import requests

from tfa.competitions import COMPETITIONS, DEPRECATED_COLUMNS, season_start_year
from tfa.ingest.matchhistory import TIMEOUT, _session

#: Columns whose presence or absence changes what can be modelled.
PROBE_COLUMNS: tuple[str, ...] = (
    "Referee",
    "HS", "AS", "HST", "AST",
    "HF", "AF", "HC", "AC",
    "HY", "AY", "HR", "AR",
    *DEPRECATED_COLUMNS,
)


@dataclass(frozen=True)
class HeaderProbe:
    competition: str
    country: str
    season: str
    available: bool
    column_count: int
    present: frozenset[str]

    def has(self, column: str) -> bool:
        return column in self.present


def probe_header(
    code: str,
    season: str,
    *,
    session: requests.Session | None = None,
) -> HeaderProbe:
    """Fetch only the header row for one competition-season.

    Streams and stops at the first newline, so auditing 11 leagues over many
    seasons costs kilobytes rather than megabytes.
    """
    comp = COMPETITIONS[code]
    session = session or _session()

    try:
        with session.get(comp.url(season), timeout=TIMEOUT, stream=True) as response:
            response.raise_for_status()
            chunk = next(response.iter_content(chunk_size=8192), b"")
    except Exception:  # noqa: BLE001 - an unavailable season is a finding, not a crash
        return HeaderProbe(code, comp.country, season, False, 0, frozenset())

    header = chunk.split(b"\n", 1)[0].decode("latin-1").strip()
    if not header:
        return HeaderProbe(code, comp.country, season, False, 0, frozenset())

    columns = [c.strip() for c in header.split(",")]
    return HeaderProbe(
        competition=code,
        country=comp.country,
        season=season,
        available=True,
        column_count=len(columns),
        present=frozenset(c for c in PROBE_COLUMNS if c in columns),
    )


def audit(
    codes: list[str],
    seasons: list[str],
    *,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Probe a grid of competition-seasons and return a tidy availability table."""
    session = session or _session()
    rows: list[dict[str, object]] = []

    for code in codes:
        comp = COMPETITIONS[code]
        for season in seasons:
            if season in comp.season_gaps:
                rows.append(
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
                continue

            probe = probe_header(code, season, session=session)
            rows.append(
                {
                    "competition": code,
                    "country": comp.country,
                    "season": season,
                    "available": probe.available,
                    "column_count": probe.column_count,
                    "known_gap": False,
                    **{c: probe.has(c) for c in PROBE_COLUMNS},
                }
            )

    return pd.DataFrame(rows)


def summarise(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-competition summary: seasons available, and which probes ever appear.

    Sorts on start year, never on the season code — see
    :func:`tfa.competitions.season_start_year` for why that distinction bites.
    """
    live = frame[frame["available"]].copy()
    live["start_year"] = live["season"].map(season_start_year)
    return live.groupby(["competition", "country"], as_index=False).agg(
        seasons_available=("season", "count"),
        first_year=("start_year", "min"),
        last_year=("start_year", "max"),
        **{c: (c, "any") for c in PROBE_COLUMNS},
    )


def deprecation_report(frame: pd.DataFrame) -> pd.DataFrame:
    """When each still-documented column actually stopped appearing.

    These are fossils, not documentation errors: every one of them was real
    once. Reporting the last season each was observed is what turns "the docs
    are wrong" into "here is exactly when the data stopped being collected".
    """
    live = frame[frame["available"]].copy()
    live["start_year"] = live["season"].map(season_start_year)

    rows = []
    for column in DEPRECATED_COLUMNS:
        seen = live[live[column]] if column in live else live.iloc[0:0]
        rows.append(
            {
                "column": column,
                "still_documented": True,
                "league_seasons_seen": int(len(seen)),
                "first_year": int(seen["start_year"].min()) if len(seen) else None,
                "last_year": int(seen["start_year"].max()) if len(seen) else None,
            }
        )
    return pd.DataFrame(rows)


#: Retained so existing callers keep working after the rename.
phantom_report = deprecation_report
