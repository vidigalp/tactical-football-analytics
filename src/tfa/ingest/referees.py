"""Portuguese match officials, harvested from zerozero.pt.

football-data.co.uk names the referee for England and Scotland only. Portugal has
none, and referee identity is a first-order confounder for anything about cards:
in England, officials with 40+ matches range from a booking multiplier of 0.59 to
1.19, a spread more than twice the size of the match-situation effect.

**Source position, stated plainly.** zerozero.pt's ``robots.txt`` disallows a
single unrelated endpoint and publishes ``sitemap_index_referees.xml``, so
referee pages are meant to be indexed. There is no AI-training clause and no bot
block. But the site footer asserts all rights reserved and refers to terms that
are named in plain text and could not be located anywhere. So this is
*permissible to access* but **not openly licensed**, and it is treated
accordingly: we harvest politely at one request per second, commit only the
factual mapping of match to official, and credit the source prominently. See
``DATA_SOURCES.md`` and ``ACKNOWLEDGEMENTS.md``.

Two endpoints, both verified:

* season roster — ``/edicao/liga-portugal/{edition}/arbitros``
* per-referee match list — ``/arbitro/{slug}/{id}/jogos-arbitrados?epoca_id={e}&compet_id_jogos=3``

Harvesting per referee rather than per match means about 230 requests for a
decade, instead of 2,800.
"""

from __future__ import annotations

import html
import logging
import re
import time
import unicodedata
from dataclasses import dataclass

import pandas as pd
import requests

log = logging.getLogger(__name__)

BASE = "https://www.zerozero.pt"
USER_AGENT = (
    "tactical-football-analytics/0.1 "
    "(+https://github.com/vidigalp/tactical-football-analytics; "
    "research; contact via GitHub issues)"
)
POLITE_DELAY = 1.0
TIMEOUT = 40

#: Liga Portugal, in zerozero's competition numbering.
COMPETITION_ID = 3

#: Season start year -> (edition id, epoca id). Verified present, 2017-18 to 2026-27.
SEASONS: dict[int, tuple[int, int]] = {
    2017: (109369, 147),
    2018: (125220, 148),
    2019: (135717, 149),
    2020: (147383, 150),
    2021: (156405, 151),
    2022: (165864, 152),
    2023: (175797, 153),
    2024: (187713, 154),
    2025: (201241, 155),
    2026: (218294, 156),
}

_REF_LINK = re.compile(r"/arbitro/([a-z0-9\-]+)/(\d+)")
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SCORE = re.compile(r"^(\d+)-(\d+)$")


@dataclass(frozen=True)
class RefereeMatch:
    date: str
    home: str
    away: str
    home_goals: int
    away_goals: int
    referee: str
    referee_id: str
    season_start: int


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _get(url: str, sess: requests.Session) -> str:
    response = sess.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    time.sleep(POLITE_DELAY)
    return response.text


def _clean(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).strip()


def normalise(name: str) -> str:
    """Fold a club name for joining across sources.

    Accents, punctuation and case vary between zerozero and football-data, so
    comparison happens on a folded form. The mapping itself still has to be
    explicit — see ``CLUB_ALIASES`` — because 'Sporting' and 'Sp Lisbon' do not
    fold to the same string and never will.
    """
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return " ".join(text.split())


def season_referees(start_year: int, sess: requests.Session) -> list[tuple[str, str]]:
    """Return (slug, id) for every official listed in a season."""
    edition, _ = SEASONS[start_year]
    text = _get(f"{BASE}/edicao/liga-portugal/{edition}/arbitros", sess)
    out: list[tuple[str, str]] = []
    for slug, ref_id in _REF_LINK.findall(text):
        if (slug, ref_id) not in out:
            out.append((slug, ref_id))
    return out


def referee_matches(
    slug: str, ref_id: str, start_year: int, sess: requests.Session
) -> list[RefereeMatch]:
    """Matches this official took in one Primeira Liga season."""
    _, epoca = SEASONS[start_year]
    url = (
        f"{BASE}/arbitro/{slug}/{ref_id}/jogos-arbitrados"
        f"?epoca_id={epoca}&compet_id_jogos={COMPETITION_ID}"
    )
    text = _get(url, sess)
    name = slug.replace("-", " ").title()

    out: list[RefereeMatch] = []
    for row in _ROW.findall(text):
        cells = [c for c in (_clean(c) for c in _CELL.findall(row)) if c]
        date = next((c for c in cells if _DATE.match(c)), None)
        if date is None:
            continue
        i = cells.index(date)
        # Layout is: date, home, score, away, ...
        if i + 3 >= len(cells):
            continue
        score = _SCORE.match(cells[i + 2])
        if not score:
            continue
        out.append(
            RefereeMatch(
                date=date,
                home=cells[i + 1],
                away=cells[i + 3],
                home_goals=int(score.group(1)),
                away_goals=int(score.group(2)),
                referee=name,
                referee_id=ref_id,
                season_start=start_year,
            )
        )
    return out


def harvest(years: list[int], sess: requests.Session | None = None) -> pd.DataFrame:
    """Harvest match officials for the given season start years."""
    sess = sess or session()
    rows: list[RefereeMatch] = []
    for year in years:
        refs = season_referees(year, sess)
        log.info("%s-%s: %d referees", year, str(year + 1)[-2:], len(refs))
        for slug, ref_id in refs:
            rows.extend(referee_matches(slug, ref_id, year, sess))
    frame = pd.DataFrame([r.__dict__ for r in rows])
    if frame.empty:
        return frame
    return frame.sort_values(["season_start", "date", "home"]).reset_index(drop=True)


def check_no_double_attribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Matches credited to more than one official.

    The strongest available accuracy signal: per-referee lists should partition
    a season cleanly. Any duplicate means the harvest, or the source, is wrong.
    """
    key = ["season_start", "date", "home", "away"]
    counts = frame.groupby(key)["referee"].nunique()
    return counts[counts > 1].reset_index(name="distinct_referees")


#: zerozero club name -> the short form football-data.co.uk uses.
#: Built by hand and validated by scoreline, not by fuzzy matching: 'Vitória FC'
#: is Setúbal while 'Vitória SC' is Guimarães, and no string metric gets that
#: right. A wrong alias here would attribute matches to the wrong club silently.
CLUB_ALIASES: dict[str, str] = {
    "FC Porto": "Porto",
    "Sporting": "Sp Lisbon",
    "SC Braga": "Sp Braga",
    "Vitória SC": "Guimaraes",
    "Vitória FC": "Setubal",
    "B SAD": "Belenenses",
    "CD Aves": "Aves",
    "CD Tondela": "Tondela",
    "Boavista FC": "Boavista",
    "Casa Pia AC": "Casa Pia",
    "Est. Amadora": "Estrela",
    "Estoril Praia": "Estoril",
    "FC Alverca": "Alverca",
    "FC Arouca": "Arouca",
    "FC Famalicão": "Famalicao",
    "FC Vizela": "Vizela",
    "GD Chaves": "Chaves",
    "Marítimo": "Maritimo",
    "Paços de Ferreira": "Pacos Ferreira",
    "Académico": "Academico Viseu",
    "AFS": "AVS",
}


def to_match_data_names(frame: pd.DataFrame) -> pd.DataFrame:
    """Translate zerozero club names into football-data's short forms."""
    out = frame.copy()
    for column in ("home", "away"):
        out[column] = out[column].map(lambda c: CLUB_ALIASES.get(c, c))
    return out


def join_to_matches(
    referees: pd.DataFrame, matches: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach officials to matches, verifying the scoreline agrees.

    Returns (joined, unmatched). The scoreline check is the point: joining on
    date and club names alone would quietly accept a wrong alias, whereas a
    mismatched score proves the two rows are different matches. Anything that
    fails is returned for inspection rather than dropped.
    """
    left = matches.copy()
    left["date"] = pd.to_datetime(left["Date"]).dt.strftime("%Y-%m-%d")

    right = to_match_data_names(referees).rename(
        columns={"home": "HomeTeam", "away": "AwayTeam"}
    )

    merged = left.merge(
        right[["date", "HomeTeam", "AwayTeam", "home_goals", "away_goals",
               "referee", "referee_id"]],
        on=["date", "HomeTeam", "AwayTeam"],
        how="left",
    )

    scored = merged["referee"].notna()
    agrees = (
        (merged["FTHG"] == merged["home_goals"])
        & (merged["FTAG"] == merged["away_goals"])
    )
    # A joined row whose score disagrees is a bad join, not a usable label.
    merged.loc[scored & ~agrees, ["referee", "referee_id"]] = pd.NA

    unmatched = merged[merged["referee"].isna()][
        ["date", "Div", "season", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]
    ]
    return merged, unmatched
