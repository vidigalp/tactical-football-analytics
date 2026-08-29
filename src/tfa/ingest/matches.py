"""Match-level ingest: column selection and odds normalisation.

Two decisions live here.

**What we keep.** The 2025-26 files carry 131 columns, of which about 12 describe
the match and the rest are betting prices. We keep the football, the referee where
present, and exactly one normalised set of match odds. `DATA_SOURCES.md` commits us
to storing only the fields this project analyses, and a 119-column odds block is not
one of them.

**How we normalise odds.** The odds are the only pre-match opponent-strength control
available in nine of eleven leagues, so they matter. But bookmaker column names
change repeatedly across 26 seasons: Pinnacle appears as ``PS``/``PSC``/``PH``,
Bet365 gains closing prices as ``B365C``, and the market aggregates move from
``BbAv`` to ``Avg``/``AvgC``. Rather than hard-code one bookmaker and silently lose
whole eras, we take the best available source per match from a documented priority
order, and record which one was used so the choice is auditable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Columns describing the match itself.
FOOTBALL_COLUMNS: tuple[str, ...] = (
    "Div", "season", "country", "Date", "HomeTeam", "AwayTeam",
    "FTHG", "FTAG", "FTR",
    "HTHG", "HTAG", "HTR",
    "HS", "AS", "HST", "AST",
    "HF", "AF", "HC", "AC",
    "HY", "AY", "HR", "AR",
    "Referee", "referee_available",
)

#: Odds triples in priority order, best first.
#:
#: Closing prices beat opening prices because they aggregate more information.
#: Market averages beat a single book because they are less exposed to one
#: firm's position. Pinnacle is preferred among single books for its low margin
#: and high limits, which make its prices unusually informative.
ODDS_PRIORITY: tuple[tuple[str, tuple[str, str, str]], ...] = (
    ("pinnacle_closing", ("PSCH", "PSCD", "PSCA")),
    ("market_avg_closing", ("AvgCH", "AvgCD", "AvgCA")),
    ("bet365_closing", ("B365CH", "B365CD", "B365CA")),
    ("pinnacle", ("PSH", "PSD", "PSA")),
    ("market_avg", ("AvgH", "AvgD", "AvgA")),
    ("betbrain_avg", ("BbAvH", "BbAvD", "BbAvA")),
    ("pinnacle_legacy", ("PH", "PD", "PA")),
    ("bet365", ("B365H", "B365D", "B365A")),
    ("william_hill", ("WHH", "WHD", "WHA")),
)


def devig(home: pd.Series, draw: pd.Series, away: pd.Series) -> pd.DataFrame:
    """Convert decimal odds to probabilities with the bookmaker margin removed.

    Uses proportional (multiplicative) normalisation: divide each implied
    probability by the overround. This is the simplest defensible method and its
    bias is well understood — it distributes the margin proportionally, which
    slightly overstates favourites relative to more elaborate schemes such as
    Shin's. Documented rather than hidden, because the choice is a modelling
    assumption and should be visible to anyone reading a result built on it.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = pd.DataFrame(
            {"home": 1.0 / home, "draw": 1.0 / draw, "away": 1.0 / away}
        )
    overround = inv.sum(axis=1)
    # An overround at or below 1 implies a risk-free arbitrage across the three
    # outcomes, which no book offers. In practice it means one leg of the triple
    # is a bad price, so the whole set is untrustworthy and the derived
    # probabilities are dropped rather than used. Observed once in 58,013 matches.
    valid = overround.notna() & (overround > 1.0)

    out = inv.div(overround, axis=0)
    out[~valid] = np.nan
    out["overround"] = overround.where(valid)
    return out


def attach_odds(frame: pd.DataFrame) -> pd.DataFrame:
    """Add normalised probabilities and a strength index.

    Picks the best available odds triple per row and records its source. A row
    with no usable odds gets NaN rather than a silent fallback — a missing
    control must stay visible to the model.
    """
    frame = frame.copy()
    n = len(frame)
    home = pd.Series(np.nan, index=frame.index)
    draw = pd.Series(np.nan, index=frame.index)
    away = pd.Series(np.nan, index=frame.index)
    source = pd.Series(pd.NA, index=frame.index, dtype="object")

    for name, (h, d, a) in ODDS_PRIORITY:
        if not all(c in frame.columns for c in (h, d, a)):
            continue
        candidate = frame[[h, d, a]].apply(pd.to_numeric, errors="coerce")
        # Only fill rows still missing, and only where the whole triple is sane.
        usable = candidate.notna().all(axis=1) & (candidate > 1.0).all(axis=1)
        fill = usable & source.isna()
        if not fill.any():
            continue
        home[fill] = candidate[h][fill]
        draw[fill] = candidate[d][fill]
        away[fill] = candidate[a][fill]
        source[fill] = name

    probs = devig(home, draw, away)
    frame["p_home"] = probs["home"]
    frame["p_draw"] = probs["draw"]
    frame["p_away"] = probs["away"]
    frame["odds_overround"] = probs["overround"]
    frame["odds_source"] = source

    # Log-odds of home win against away win: a signed, symmetric pre-match
    # strength gap, zero when the teams are priced level. Draw probability
    # cancels, so this is unaffected by how draw-heavy a league is.
    with np.errstate(divide="ignore", invalid="ignore"):
        frame["strength_diff"] = np.log(frame["p_home"] / frame["p_away"])
    frame.loc[~np.isfinite(frame["strength_diff"]), "strength_diff"] = np.nan

    assert len(frame) == n
    return frame


def select_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the football, the referee, and the normalised odds. Drop the rest."""
    derived = [
        "p_home", "p_draw", "p_away", "odds_overround", "odds_source", "strength_diff",
    ]
    keep = [c for c in (*FOOTBALL_COLUMNS, *derived) if c in frame.columns]
    return frame[keep].copy()


def tidy(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce counts to integers and drop rows that are not matches."""
    frame = frame.copy()
    counts = [
        "FTHG", "FTAG", "HTHG", "HTAG",
        "HS", "AS", "HST", "AST",
        "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR",
    ]
    for column in counts:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")

    required = [c for c in ("HF", "AF", "HY", "AY") if c in frame.columns]
    if required:
        frame = frame[frame[required].notna().all(axis=1)]

    return frame.reset_index(drop=True)


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """Full per-file pipeline: odds, column selection, tidying."""
    return tidy(select_columns(attach_odds(frame)))


def to_team_match(frame: pd.DataFrame) -> pd.DataFrame:
    """Reshape one row per match into one row per team per match.

    This is the shape every model in this project wants: the share-of-match
    models need a team and its opponent side by side, and the conditional-rate
    models need each team's own denominator.
    """
    shared = [
        "Div", "season", "country", "Date", "Referee",
        "odds_source", "odds_overround",
    ]
    shared = [c for c in shared if c in frame.columns]

    def side(is_home: bool) -> pd.DataFrame:
        me, them = ("H", "A") if is_home else ("A", "H")
        out = frame[shared].copy()
        out["team"] = frame["HomeTeam"] if is_home else frame["AwayTeam"]
        out["opponent"] = frame["AwayTeam"] if is_home else frame["HomeTeam"]
        out["is_home"] = is_home

        for name, code in (
            ("goals", "FTG"), ("shots", "S"), ("shots_on_target", "ST"),
            ("fouls", "F"), ("corners", "C"), ("yellows", "Y"), ("reds", "R"),
        ):
            mine = f"{me}{code}" if code != "FTG" else f"FT{me}G"
            theirs = f"{them}{code}" if code != "FTG" else f"FT{them}G"
            out[name] = frame[mine]
            out[f"opp_{name}"] = frame[theirs]

        # Signed strength gap from this team's perspective.
        out["strength_diff"] = (
            frame["strength_diff"] if is_home else -frame["strength_diff"]
        )
        out["p_win"] = frame["p_home"] if is_home else frame["p_away"]
        return out

    stacked = pd.concat([side(True), side(False)], ignore_index=True)
    return stacked.sort_values(["Div", "season", "Date", "team"]).reset_index(drop=True)
