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

from tfa.competitions import COMPETITIONS, CORE_COLUMNS, Competition

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


def _parse(raw: bytes, comp: Competition, season: str) -> pd.DataFrame:
    # These files carry trailing blank columns and occasional ragged rows;
    # python engine tolerates them, and encoding is latin-1 in older seasons.
    frame = pd.read_csv(
        io.BytesIO(raw),
        encoding="latin-1",
        on_bad_lines="skip",
        engine="python",
    )
    frame = frame.loc[:, [c for c in frame.columns if not str(c).startswith("Unnamed")]]
    frame = frame.dropna(how="all")
    # A row without a home team is padding, not a match.
    if "HomeTeam" in frame.columns:
        frame = frame[frame["HomeTeam"].notna()]

    missing = [c for c in CORE_COLUMNS if c not in frame.columns]
    if missing:
        raise SchemaError(
            f"{comp.code} {season}: missing required columns {missing}. "
            "Upstream schema may have changed — investigate before trusting any result."
        )

    frame = frame.copy()
    frame["Div"] = comp.code
    frame["season"] = season
    frame["country"] = comp.country
    frame["referee_available"] = comp.referee_available
    if "Referee" not in frame.columns:
        frame["Referee"] = pd.NA

    frame["Date"] = pd.to_datetime(frame["Date"], dayfirst=True, errors="coerce")
    return frame.reset_index(drop=True)


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
