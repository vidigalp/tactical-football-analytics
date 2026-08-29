"""football-data.co.uk ingest — the primary, committed source.

Deliberately implemented with ``requests`` + ``pandas`` rather than via
``soccerdata``: the files are plain CSVs, the library's built-in league dict
covers only the Big-5 (verified — Portugal and the other five countries are
absent), and keeping the critical path dependency-light means the reproducible
run needs nothing beyond the core dependencies.

Nothing here scrapes a site that forbids it. See ``DATA_SOURCES.md``.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass

import pandas as pd
import requests

from tfa.competitions import (
    COMPETITIONS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    Competition,
)

log = logging.getLogger(__name__)

USER_AGENT = (
    "tactical-football-analytics/0.1 "
    "(+https://github.com/vidigalp/tactical-football-analytics)"
)
TIMEOUT = 30


class SchemaError(RuntimeError):
    """Raised when a fetched file lacks columns this project depends on.

    Deliberately fatal. A silently missing column is exactly how a pipeline
    starts publishing wrong numbers.
    """


@dataclass(frozen=True)
class Fetched:
    competition: str
    season: str
    url: str
    raw: bytes
    frame: pd.DataFrame


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_csv(
    comp: Competition,
    season: str,
    *,
    session: requests.Session | None = None,
    retries: int = 3,
    backoff: float = 2.0,
) -> Fetched:
    """Fetch one competition-season CSV.

    Retries on transient failures — ``soccerdata`` has hit 503s from this host —
    and fails closed rather than returning a partial frame.
    """
    session = session or _session()
    url = comp.url(season)

    raw: bytes | None = None
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            raw = response.content
            break
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised below
            last = exc
            log.warning("fetch failed (%s/%s) for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)

    if raw is None:
        raise RuntimeError(f"failed to fetch {url} after {retries} attempts") from last

    frame = _parse(raw, comp, season)
    return Fetched(competition=comp.code, season=season, url=url, raw=raw, frame=frame)


def _decode(raw: bytes) -> str:
    """Decode a season file, handling a quarter-century of encoding drift.

    Recent files are UTF-8 with a byte-order mark; older ones are latin-1 and
    are not valid UTF-8. Decoding everything as latin-1 turns the BOM into a
    literal ``ï»¿`` glued to the first column name, so ``Div`` silently becomes
    ``ï»¿Div`` and the file appears to be missing a required column. Decoding
    everything as UTF-8 instead throws on the older files.

    Neither can be assumed, and getting it wrong the other way would mangle
    accented team names — which would then fail to match across seasons.
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _parse(raw: bytes, comp: Competition, season: str) -> pd.DataFrame:
    # These files carry trailing blank columns and occasional ragged rows, so
    # the python engine is used for its tolerance of both.
    frame = pd.read_csv(
        io.StringIO(_decode(raw)),
        on_bad_lines="skip",
        engine="python",
    )
    frame.columns = [str(c).strip().lstrip("﻿") for c in frame.columns]
    frame = frame.loc[:, [c for c in frame.columns if not str(c).startswith("Unnamed")]]
    frame = frame.dropna(how="all")
    # A row without a home team is padding, not a match.
    if "HomeTeam" in frame.columns:
        frame = frame[frame["HomeTeam"].notna()]

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise SchemaError(
            f"{comp.code} {season}: missing required columns {missing}. "
            "Upstream schema may have changed — investigate before trusting any result."
        )

    frame = frame.copy()
    # Optional columns are filled rather than demanded, so a file with fouls but
    # no shots is still usable for discipline work. Which columns were absent
    # stays visible in the data as NA rather than being silently zero.
    for column in OPTIONAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["Div"] = comp.code
    frame["season"] = season
    frame["country"] = comp.country
    frame["referee_available"] = comp.referee_available
    if "Referee" not in frame.columns:
        frame["Referee"] = pd.NA

    frame["Date"] = _parse_dates(frame["Date"])
    return frame.reset_index(drop=True)


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates that are dd/mm/yy in older files and dd/mm/yyyy in newer ones.

    Tried explicitly rather than inferred, because inference is per-element and
    a two-digit year is ambiguous enough that pandas can silently disagree with
    itself between rows of the same file.
    """
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        if parsed.notna().mean() > 0.95:
            return parsed
    return pd.to_datetime(series, dayfirst=True, errors="coerce")


def fetch_many(
    codes: list[str],
    seasons: list[str],
    *,
    session: requests.Session | None = None,
    polite_delay: float = 0.5,
) -> list[Fetched]:
    """Fetch a grid of competition-seasons, skipping known gaps."""
    session = session or _session()
    out: list[Fetched] = []
    for code in codes:
        comp = COMPETITIONS[code]
        for season in seasons:
            if season in comp.season_gaps:
                log.info("skipping known gap %s %s", code, season)
                continue
            out.append(fetch_csv(comp, season, session=session))
            time.sleep(polite_delay)
    return out
