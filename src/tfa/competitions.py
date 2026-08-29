"""Competition registry for football-data.co.uk.

Every fact in this module was verified empirically by auditing the live CSV
headers (see `tests/test_competitions.py` and the Week 1 header audit), not
taken from the site's own `notes.txt`, which over-advertises several columns.

Verified 2026-08-29 by auditing 363 competition-seasons (1993-2025):

* **Match statistics begin in 2000-01.** Earlier files carry results and odds
  only, so the analytic window is 26 seasons, not 33.
* **Match statistics were never backfilled.** They arrived league by league
  over seventeen years: England, Scotland and Germany from 2000, Italy and
  Spain 2005, France 2007, Netherlands/Portugal/Turkey 2017, Belgium and
  Greece 2019. A file existing tells you nothing about it being usable.
  Only 179 of 286 league-seasons in 2000-2025 carry fouls and cards.
* Germany's series is **interrupted**: present 2000-2002, absent 2002-03,
  continuous from 2003-04. Its referee column covers only those first two
  seasons, so the richer early file was lost and only partly restored.
* ``Referee`` coverage **narrowed over time**. England: continuous 2000-2025.
  Scotland: 2000-2011 and 2013-2025 (2012 missing). Germany: 2000-2001 only.
  Italy: 2005-2006 only. Two associations gained and then lost it.
* ``HO/AO``, ``HHW/AHW``, ``HBP/ABP`` were present in 2000-01 and dropped;
  ``HFKC/AFKC`` survived to 2017-18. ``notes.txt`` still documents all of them.
  They are fossils, not documentation errors.
* Median column count: 61 (2018) -> 105 (2019) -> 131 (2025). The files more
  than doubled in width while football content shrank; the growth is odds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BASE_URL = "https://www.football-data.co.uk/mmz4281"

#: Columns without which a file cannot be used at all: match identity, result,
#: and the discipline counts this project is built around. Absence is fatal.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "Div", "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",
    "HF", "AF", "HY", "AY", "HR", "AR",
)

#: Present in most files but not all, and not required. Germany 2003-2005 carries
#: fouls and cards without shots on target; discarding three seasons of real
#: discipline data over a missing shooting column would be the wrong trade.
#: Missing values are filled with NA so the schema stays rectangular.
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "HS", "AS", "HST", "AST", "HC", "AC",
    "HTHG", "HTAG", "HTR",
)

#: Everything the analysis may touch.
CORE_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

#: The first season carrying match statistics. Earlier files are results+odds only.
FIRST_STATS_SEASON_YEAR = 2000

#: Documented by football-data.co.uk but long since dropped from live files.
#: Kept here so a future contributor cannot build on a column that no longer
#: exists, and so the Week 1 audit can report exactly when each disappeared.
DEPRECATED_COLUMNS: tuple[str, ...] = (
    "HO", "AO",        # offsides — last seen 2000-01
    "HHW", "AHW",      # hit woodwork — last seen 2000-01
    "HBP", "ABP",      # bookings points — last seen 2000-01
    "HFKC", "AFKC",    # free kicks conceded — last seen 2017-18
)

#: Backwards-compatible alias. The original name was wrong: these columns are
#: historical, not imaginary.
PHANTOM_COLUMNS = DEPRECATED_COLUMNS


@dataclass(frozen=True)
class Competition:
    """One division on football-data.co.uk."""

    code: str
    """football-data.co.uk division code, e.g. ``E0``."""

    name: str
    country: str

    referee_available: bool
    """Whether ``Referee`` appears in recent seasons. Verified, not assumed.

    Note this is a *current-era* flag. Germany and Italy carried a referee
    column briefly (2000-01 and 2005-06) and lost it; see ``audit`` for the
    per-season truth.
    """

    first_season: str
    """Earliest season code for which a file exists at all."""

    discipline_from: int = 0
    """First season *start year* with fouls and cards present, verified by audit.

    Match statistics were not backfilled: they arrived league by league over
    seventeen years. A file existing says nothing about it being usable.
    """

    full_core_from: int = 0
    """First season start year with the complete core bundle, including shots on target."""

    discipline_gaps: tuple[str, ...] = ()
    """Seasons inside the discipline window where the file exists but has no fouls/cards."""

    season_gaps: tuple[str, ...] = ()
    """Season codes known to be missing or unusable."""

    referee_gaps: tuple[str, ...] = ()
    """Seasons where the file exists but carries no ``Referee`` column."""

    notes: tuple[str, ...] = field(default_factory=tuple)

    def url(self, season: str) -> str:
        """Return the CSV URL for a season code such as ``2526``."""
        return f"{BASE_URL}/{season}/{self.code}.csv"


#: The second-yellow convention differs by country and is a classic silent
#: discrepancy when comparing sources. Per football-data.co.uk's own notes,
#: English and Scottish yellow-card counts exclude the first yellow of a
#: second-bookable offence (it is folded into the red), while other countries
#: count both. There is no dedicated second-yellow column anywhere.
SECOND_YELLOW_FOLDED_INTO_RED: frozenset[str] = frozenset({"E0", "SC0"})

COMPETITIONS: dict[str, Competition] = {
    c.code: c
    for c in (
        Competition("E0", "Premier League", "England", True, "9394",
                    discipline_from=2000, full_core_from=2000,
                    notes=("Referee available.",
                           "Yellows exclude the first of a second-bookable offence.")),
        Competition("SC0", "Premiership", "Scotland", True, "9495",
                    discipline_from=2000, full_core_from=2000,
                    referee_gaps=("1213",),
                    notes=("Referee available except 2012-13.",
                           "Yellows exclude the first of a second-bookable offence.")),
        # Germany is the one interrupted series: fouls and cards are present in
        # 2000-01 and 2001-02, absent in 2002-03, and continuous from 2003-04.
        # The same two early seasons are the only ones carrying a referee column,
        # so the whole richer file was lost and only partly restored.
        Competition("D1", "Bundesliga", "Germany", False, "9394",
                    discipline_from=2000, full_core_from=2006,
                    discipline_gaps=("0203",),
                    notes=("Fouls and cards interrupted in 2002-03.",)),
        Competition("I1", "Serie A", "Italy", False, "9394",
                    discipline_from=2005, full_core_from=2005),
        Competition("SP1", "La Liga", "Spain", False, "9394",
                    discipline_from=2005, full_core_from=2005),
        Competition("F1", "Ligue 1", "France", False, "9394",
                    discipline_from=2007, full_core_from=2007),
        Competition("P1", "Primeira Liga", "Portugal", False, "9495",
                    discipline_from=2017, full_core_from=2017,
                    season_gaps=("9798", "9899", "9900"),
                    notes=("Portugal has no files for 1997-98 through 1999-2000.",)),
        Competition("N1", "Eredivisie", "Netherlands", False, "9394",
                    discipline_from=2017, full_core_from=2017),
        Competition("B1", "Pro League", "Belgium", False, "9495",
                    discipline_from=2019, full_core_from=2019),
        Competition("T1", "Süper Lig", "Turkey", False, "9495",
                    discipline_from=2017, full_core_from=2017),
        Competition("G1", "Super League", "Greece", False, "9495",
                    discipline_from=2019, full_core_from=2019),
    )
}

#: Divisions where the referee is observable, so a referee effect can be
#: estimated directly rather than conditioned out.
REFEREE_LEAGUES: tuple[str, ...] = tuple(
    c.code for c in COMPETITIONS.values() if c.referee_available
)

#: Understat enrichment (xG, npxG, PPDA, deep completions) covers the Big-5 only.
UNDERSTAT_LEAGUES: tuple[str, ...] = ("E0", "D1", "I1", "SP1", "F1")


def season_code(start_year: int) -> str:
    """Return the football-data.co.uk season code for a season starting in *start_year*.

    >>> season_code(2025)
    '2526'
    """
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_start_year(code: str) -> int:
    """Inverse of :func:`season_code`.

    Season codes must never be sorted as strings: ``"0001"`` (2000-01) sorts
    before ``"9394"`` (1993-94) lexicographically, which silently reverses any
    chronological summary. Always sort on this instead.

    >>> season_start_year("2526"), season_start_year("9394")
    (2025, 1993)
    """
    first = int(code[:2])
    return 1900 + first if first >= 93 else 2000 + first


def seasons_range(start_year: int, end_year: int) -> list[str]:
    """Return season codes for seasons starting in ``start_year..end_year`` inclusive."""
    return [season_code(y) for y in range(start_year, end_year + 1)]


def available_seasons(code: str, start_year: int, end_year: int) -> list[str]:
    """Season codes for *code*, excluding that competition's known gaps."""
    comp = COMPETITIONS[code]
    return [s for s in seasons_range(start_year, end_year) if s not in comp.season_gaps]


def usable_seasons(
    code: str,
    end_year: int = 2025,
    *,
    require_full_core: bool = False,
) -> list[str]:
    """Season codes for *code* that actually carry the statistics we model.

    Always prefer this over :func:`available_seasons` when selecting data for
    analysis. The difference between "a file exists" and "the file has fouls in
    it" is 109 league-seasons.
    """
    comp = COMPETITIONS[code]
    start = comp.full_core_from if require_full_core else comp.discipline_from
    if not start:
        return []
    return [
        s
        for s in available_seasons(code, start, end_year)
        if s not in comp.discipline_gaps
    ]
