"""The season in progress, every league, every club, as a dataset the site can draw.

The studies are dated and finished. This is the thing that changes: once a week
the newest snapshot is read, every club in every league is placed against the
same booking model the live page uses, and the result is written as JSON the
site serves same-origin. No ranking is computed here and none should be drawn
from it. Every club gets its estimate, its interval, and its place in the spread
of clubs measured the same way, and the reader does the comparing.

Three files, so a page loads only what it draws:

``dashboard/meta.json``
    Provenance, the frozen model per league, sources and caveats.
``dashboard/current.json``
    The season in progress. Every club with every match played so far and the
    cumulative index after each one, with a Poisson interval, so a trajectory
    can be drawn. League and Europe-wide percentiles, and the same-matchweek
    distribution of every completed team-season for the reader to stand the
    current one against.
``dashboard/history/{league}.json``
    Every completed season of one league. Club-season totals, index and
    interval, the shrunk estimate from study 04's gamma-Poisson prior, and the
    cumulative index by matchweek. League-season rates by matchweek too, so a
    season can be read against earlier ones at the same point.

The model is the one in ``scripts/season_status.py`` and the pre-registration of
2026-08-30, generalised to eleven leagues. For each league an affine expectation
``a + b x fouls`` is fitted on completed seasons from 2017-18 onward, and a
situation multiplier per pre-match strength band on the same window. For
Portugal that reproduces the frozen coefficients exactly, which
``tests/test_dashboard.py`` asserts. Completed seasons use their own league-season
affine fit, as the studies do, with the league's situation multiplier.

The window starts at 2017-18 because it is where all eleven leagues carry fouls
and cards, and because the game changed at about that point: pooling the
Premier League of 2000-01 with the one of 2025-26 would price today's cards with
a rate from a different sport.

Run: uv run python scripts/season_dashboard.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from evidence.shrinkage import GammaPoissonPrior, gamma_poisson_prior, shrink_gamma_poisson
from tfa.competitions import COMPETITIONS, CURRENT_SEASON, season_start_year
from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest
from tfa.stats.expectation import fit as fit_era_models

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"

#: First season of the baseline window, in football-data's coding.
BASELINE_FROM = 2017

#: Pre-match role from the devigged odds, as study 02 defines it.
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]

#: The false-discovery rate of the within-league screen, METHODS.md section 5.
FDR = 0.10

#: A team-season is complete once it has this many matches.
COMPLETE = 30

QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]

SOURCES = [
    {
        "name": "football-data.co.uk",
        "url": "https://www.football-data.co.uk/",
        "covers": "match results, fouls, cards, shots, corners and closing odds, eleven leagues",
        "licence": "free for personal and research use, attribution requested",
        "attribution": "football-data.co.uk",
    },
]

CAVEATS = [
    "A booking index of 1.0 means as many yellow cards as the model expects from the fouls "
    "recorded and the pre-match situation. It is not a measure of fairness and is never read "
    "that way here.",
    "Fouls and cards are as recorded by the source feed. What counts as a foul is not the same "
    "in every league, which is why every expectation is fitted within the league.",
    "Intervals are exact Poisson intervals on the count of yellow cards. Early in a season they "
    "are wide enough to admit almost anything, and that is the point of showing them.",
    "Percentiles say where a club sits among clubs measured the same way. Nothing here is a "
    "ranking, and a sorted list drawn from this file would be one.",
    "The situation multiplier needs odds. A match without them is priced at the era "
    "expectation alone.",
    "Completed seasons use their own league-season fit. The season in progress uses the "
    "league's pooled fit on completed seasons since 2017-18, frozen, so four matches cannot "
    "set their own baseline.",
]


def season_label(code: str) -> str:
    return f"20{code[:2]}-{code[2:]}"


def load(snapshot: Path) -> pd.DataFrame:
    entries = [e for e in read_manifest(snapshot) if e.source == "football-data"]
    frame = pd.concat(
        [pd.read_parquet(snapshot / e.parquet_path) for e in entries], ignore_index=True
    )
    return frame.dropna(subset=["HF", "AF", "HY", "AY"])


def interval(observed: np.ndarray, expected: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    observed = np.asarray(observed, dtype=float)
    expected = np.asarray(expected, dtype=float)
    low = np.where(observed > 0, stats.chi2.ppf(0.025, 2 * observed) / 2, 0.0)
    high = stats.chi2.ppf(0.975, 2 * (observed + 1)) / 2
    return low / expected, high / expected


def two_sided_poisson(observed: np.ndarray, expected: np.ndarray) -> np.ndarray:
    observed = np.asarray(observed, dtype=float)
    expected = np.asarray(expected, dtype=float)
    lower = stats.poisson.cdf(observed, expected)
    upper = 1 - stats.poisson.cdf(observed - 1, expected)
    return np.clip(2 * np.minimum(lower, upper), 0, 1)


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    ranked = p.sort_values()
    count = len(ranked)
    adjusted = (ranked * count / np.arange(1, count + 1))[::-1].cummin()[::-1].clip(upper=1)
    return adjusted.reindex(p.index)


def num(value: float, digits: int = 3) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


def ints(series: pd.Series) -> int | None:
    total = series.sum(min_count=1)
    return None if pd.isna(total) else int(total)


def band_summary(rows: pd.DataFrame, band: dict[str, dict]) -> dict[str, float | int | None]:
    """How often a completed team-season leaves its own pool's 5th-95th band.

    By construction a tenth of seasons sit outside the band at any one match. The
    share that steps outside at some point is a different number, and the site
    should quote it rather than guess it.
    """
    lo = rows.n.map(lambda k: band[str(k)]["p05"])
    hi = rows.n.map(lambda k: band[str(k)]["p95"])
    outside = (rows.cum_index < lo) | (rows.cum_index > hi)
    per_season = outside.groupby([rows[k] for k in ["Div", "season", "team"]]).agg(["any", "last"])
    return {
        "team_seasons": int(len(per_season)),
        "ever_outside_pct": num(per_season["any"].mean() * 100, 1),
        "outside_at_end_pct": num(per_season["last"].mean() * 100, 1),
    }


def quantile_rows(values: pd.Series) -> dict[str, float | int | None]:
    """Quantiles of the pool plus its size, which shrinks past the shortest season."""
    row: dict[str, float | int | None] = {
        f"p{int(q * 100):02d}": num(values.quantile(q)) for q in QUANTILES}
    row["n"] = int(len(values))
    return row


def league_models(history: pd.DataFrame) -> tuple[float, float, dict[str, float]]:
    """Pooled affine fit and situation multiplier for one league's baseline window."""
    slope, intercept = np.polyfit(history.fouls, history.yellows, 1)
    if intercept < 0:
        slope, intercept = history.yellows.sum() / history.fouls.sum(), 0.0
    expected = intercept + slope * history.fouls
    band = pd.cut(history.strength_diff, BANDS, labels=NAMES)
    with_odds = history.strength_diff.notna()
    multiplier = {
        name: float(history.yellows[with_odds & (band == name)].sum()
                    / expected[with_odds & (band == name)].sum())
        for name in NAMES
    }
    return float(intercept), float(slope), multiplier


def attach_expectation(teams: pd.DataFrame, intercept: pd.Series, slope: pd.Series,
                       multiplier: dict[str, float]) -> pd.DataFrame:
    out = teams.copy()
    out["expected_era"] = intercept.to_numpy() + slope.to_numpy() * out.fouls.to_numpy()
    out["band"] = pd.cut(out.strength_diff, BANDS, labels=NAMES).astype(object)
    out["expected"] = out.expected_era * out.band.map(multiplier).astype(float).fillna(1.0)
    return out


def cumulative(scored: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Cumulative counts and index after each match, within each team-season."""
    out = scored.sort_values(keys + ["n"]).copy()
    grouped = out.groupby(keys)
    out["cum_fouls"] = grouped.fouls.cumsum()
    out["cum_yellows"] = grouped.yellows.cumsum()
    reds = out.reds.fillna(0)
    out["cum_cards"] = out.cum_yellows + reds.groupby([out[k] for k in keys]).cumsum()
    out["cum_expected"] = grouped.expected.cumsum()
    out["cum_index"] = out.cum_yellows / out.cum_expected
    out["cum_cards_per_foul"] = (out.cum_cards / out.cum_fouls).astype("float64")
    lo, hi = interval(out.cum_yellows, out.cum_expected)
    out["cum_lo"], out["cum_hi"] = lo, hi
    return out


def cards_per_foul(rows: pd.DataFrame) -> float | None:
    """All cards over fouls: yellows plus reds as football-data records them.

    football-data has no second-yellow column. In England and Scotland a
    second-yellow dismissal is recorded as one red only; elsewhere it is one
    yellow and one red, so it counts twice here (DATA_SOURCES.md). One
    team-match in the history has no red count and contributes zero reds.
    """
    return num((rows.yellows.sum() + rows.reds.sum()) / rows.fouls.sum(), 4)


def club_totals(group: pd.DataFrame) -> dict[str, int | None]:
    return {
        "matches": int(len(group)),
        "fouls": ints(group.fouls),
        "yellows": ints(group.yellows),
        "reds": ints(group.reds),
        "goals": ints(group.goals),
        "goals_against": ints(group.opp_goals),
        "shots": ints(group.shots),
        "shots_on_target": ints(group.shots_on_target),
        "corners": ints(group.corners),
        "wins": int((group.goals > group.opp_goals).sum()),
        "draws": int((group.goals == group.opp_goals).sum()),
        "losses": int((group.goals < group.opp_goals).sum()),
        "home_matches": int(group.is_home.sum()),
        "with_odds": int(group.strength_diff.notna().sum()),
    }


def by_matchweek_rates(rows: pd.DataFrame) -> dict[str, list[float | None]]:
    """League-level cumulative rates after each team's k-th match.

    Rates are per match, both sides counted, so "yellows per match" reads the way
    a match report would. The rows are team-matches, two per match.
    """
    ordered = rows.sort_values("n")
    grouped = ordered.groupby("n").agg(fouls=("fouls", "sum"), yellows=("yellows", "sum"),
                                      reds=("reds", "sum"), matches=("fouls", "size"))
    cum = grouped.cumsum()
    cum["matches"] = cum.matches / 2
    return {
        "yellows_per_match": [num(v) for v in cum.yellows / cum.matches],
        "fouls_per_match": [num(v) for v in cum.fouls / cum.matches],
        "reds_per_match": [num(v) for v in cum.reds / cum.matches],
        "cards_per_foul": [num(v, 4) for v in (cum.yellows + cum.reds) / cum.fouls],
    }


def main() -> None:
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    manifest = json.loads((snapshot / "manifest.json").read_text())
    teams = to_team_match(load(snapshot)).dropna(subset=["fouls", "yellows"])
    teams["year"] = teams.season.map(season_start_year)
    keys = ["Div", "season", "team"]
    teams = teams.sort_values(keys + ["Date"])
    teams["n"] = teams.groupby(keys).cumcount() + 1

    completed = teams[teams.season != CURRENT_SEASON]
    current = teams[teams.season == CURRENT_SEASON]

    # Completed seasons keep their own league-season fit, as the studies do.
    era = fit_era_models(completed.rename(columns={"Div": "league"}))

    leagues: dict[str, dict] = {}
    history_out: dict[str, dict] = {}
    scored_current: list[pd.DataFrame] = []
    scored_completed: list[pd.DataFrame] = []

    for code in sorted(COMPETITIONS):
        comp = COMPETITIONS[code]
        done = completed[completed.Div == code]
        now = current[current.Div == code]
        if done.empty:
            continue
        baseline = done[done.year >= BASELINE_FROM]
        intercept, slope, multiplier = league_models(baseline)

        # Era expectation per completed team-match from its own league-season fit.
        model = done.season.map(lambda s: era[(code, s)])  # noqa: B023
        done_scored = attach_expectation(
            done, model.map(lambda m: m.intercept), model.map(lambda m: m.slope), multiplier)
        done_scored = cumulative(done_scored, keys)
        scored_completed.append(done_scored)

        # Study 04's prior on the completed club-seasons of this league.
        seasons = done_scored.groupby(keys).agg(
            yellows=("yellows", "sum"), expected=("expected", "sum"), matches=("n", "size"))
        full = seasons[seasons.matches >= COMPLETE]
        prior: GammaPoissonPrior = gamma_poisson_prior(full.yellows, full.expected)

        if not now.empty:
            now_scored = attach_expectation(
                now, pd.Series(intercept, index=now.index),
                pd.Series(slope, index=now.index), multiplier)
            now_scored = cumulative(now_scored, keys)
            now_scored["prior_shape"], now_scored["prior_rate"] = prior.shape, prior.rate
            scored_current.append(now_scored)

        leagues[code] = {
            "code": code, "name": comp.name, "country": comp.country,
            "completed_seasons": sorted(done.season.unique().tolist()),
            "baseline_seasons": sorted(baseline.season.unique().tolist()),
            "model": {"intercept": num(intercept, 6), "slope": num(slope, 6),
                      "team_matches": int(len(baseline))},
            "situation_multiplier": {k: num(v) for k, v in multiplier.items()},
            "prior": {"shape": num(prior.shape, 4), "rate": num(prior.rate, 4),
                      "detectable_variance": bool(prior.detectable_variance),
                      "club_seasons": int(len(full))},
            "clubs_current": int(now.team.nunique()),
            "matches_current": int(len(now) // 2),
            "latest_date": None if now.empty else str(now.Date.max())[:10],
        }

        # History file for this league.
        shrunk = shrink_gamma_poisson(seasons.yellows, seasons.expected, prior)
        shrunk.index = seasons.index
        lo, hi = interval(seasons.yellows, seasons.expected)
        seasons["lo"], seasons["hi"] = lo, hi
        history_seasons: dict[str, dict] = {}
        for season in sorted(done.season.unique()):
            rows = done_scored[done_scored.season == season]
            clubs = {}
            for team, group in rows.groupby("team"):
                key = (code, season, team)
                s = shrunk.loc[key]
                clubs[str(team)] = {
                    **club_totals(group),
                    "expected": num(group.expected.sum(), 2),
                    "index": num(group.yellows.sum() / group.expected.sum()),
                    "lo": num(seasons.loc[key, "lo"]), "hi": num(seasons.loc[key, "hi"]),
                    "shrunk": num(s.shrunk), "shrunk_lo": num(s.lower),
                    "shrunk_hi": num(s.upper), "reliability": num(s.reliability),
                    "complete": bool(len(group) >= COMPLETE),
                    "cum_index": [num(v) for v in group.sort_values("n").cum_index],
                    "cards_per_foul": cards_per_foul(group),
                    "cum_cards_per_foul": [
                        num(v, 4) for v in group.sort_values("n").cum_cards_per_foul],
                }
            model_fit = era[(code, season)]
            history_seasons[season] = {
                "label": season_label(season),
                "matches": int(len(rows) // 2),
                "clubs": clubs,
                "model": {"intercept": num(model_fit.intercept, 6),
                          "slope": num(model_fit.slope, 6)},
                "yellows": ints(rows.yellows), "fouls": ints(rows.fouls), "reds": ints(rows.reds),
                "cards_per_foul": cards_per_foul(rows),
                "by_matchweek": by_matchweek_rates(rows),
            }
        full_rows = done_scored.set_index(keys).loc[full.index].reset_index()
        # The spread of every completed team-season after k matches. The
        # reader stands the current one against this, not against a rank.
        band = {str(k): quantile_rows(g.cum_index) for k, g in full_rows.groupby("n")}
        history_out[code] = {
            "league": code,
            "seasons": history_seasons,
            "cum_index_by_matchweek": band,
            "band_summary": band_summary(full_rows, band),
        }

    all_current = pd.concat(scored_current, ignore_index=True)
    all_completed = pd.concat(scored_completed, ignore_index=True)
    full_completed = all_completed.merge(
        all_completed.groupby(keys).n.max().rename("length").reset_index(), on=keys)
    full_completed = full_completed[full_completed.length >= COMPLETE]

    # Club-level current state, every league in one frame for the percentiles.
    club_now = all_current.groupby(keys).agg(
        matches=("n", "max"), yellows=("yellows", "sum"), expected=("expected", "sum"),
        expected_era=("expected_era", "sum"), prior_shape=("prior_shape", "first"),
        prior_rate=("prior_rate", "first"))
    club_now["index"] = club_now.yellows / club_now.expected
    club_now["p"] = two_sided_poisson(club_now.yellows, club_now.expected)
    club_now["bh"] = club_now.groupby(level="Div", group_keys=False).p.apply(benjamini_hochberg)
    # Share of clubs at or below this index, the club itself included, so the
    # site can say "X% of the N clubs are at or below" and mean exactly that.
    def at_or_below(values: pd.Series) -> pd.Series:
        return values.map(lambda x: float((values <= x).mean() * 100))

    club_now["europe_percentile"] = at_or_below(club_now["index"])
    club_now["league_percentile"] = club_now.groupby(level="Div", group_keys=False)["index"].apply(
        at_or_below)
    lo, hi = interval(club_now.yellows, club_now.expected)
    club_now["lo"], club_now["hi"] = lo, hi
    post_shape = club_now.prior_shape + club_now.yellows
    post_rate = club_now.prior_rate + club_now.expected
    club_now["shrunk"] = post_shape / post_rate
    club_now["shrunk_lo"] = stats.gamma.ppf(0.025, post_shape, scale=1 / post_rate)
    club_now["shrunk_hi"] = stats.gamma.ppf(0.975, post_shape, scale=1 / post_rate)
    club_now["reliability"] = club_now.expected / (club_now.prior_rate + club_now.expected)

    # Same-matchweek percentile against every completed team-season, in the
    # league and across Europe. This is what "outlier or early noise" needs.
    def same_point(row: pd.Series, pool: pd.DataFrame) -> float:
        at = pool[pool.n == row.matches].cum_index
        return float("nan") if at.empty else float((at <= row["index"]).mean() * 100)

    current_leagues: dict[str, dict] = {}
    for code, group in all_current.groupby("Div"):
        pool_league = full_completed[full_completed.Div == code]
        clubs = {}
        for team, matches in group.groupby("team"):
            row = club_now.loc[(code, CURRENT_SEASON, team)]
            matches = matches.sort_values("n")
            clubs[str(team)] = {
                **club_totals(matches),
                "expected": num(row.expected, 2), "expected_era": num(row.expected_era, 2),
                "index": num(row["index"]), "lo": num(row.lo), "hi": num(row.hi),
                "p": num(row.p, 4), "bh": num(row.bh, 4), "survives_bh": bool(row.bh < FDR),
                "shrunk": num(row.shrunk), "shrunk_lo": num(row.shrunk_lo),
                "shrunk_hi": num(row.shrunk_hi), "reliability": num(row.reliability),
                "league_percentile": num(row.league_percentile, 1),
                "europe_percentile": num(row.europe_percentile, 1),
                "league_history_percentile": num(same_point(row, pool_league), 1),
                "europe_history_percentile": num(same_point(row, full_completed), 1),
                "cards_per_foul": cards_per_foul(matches),
                "by_match": [
                    {
                        "n": int(m.n), "date": str(m.Date)[:10], "opponent": str(m.opponent),
                        "home": bool(m.is_home), "fouls": int(m.fouls), "yellows": int(m.yellows),
                        "reds": None if pd.isna(m.reds) else int(m.reds),
                        "goals": None if pd.isna(m.goals) else int(m.goals),
                        "goals_against": None if pd.isna(m.opp_goals) else int(m.opp_goals),
                        "shots": None if pd.isna(m.shots) else int(m.shots),
                        "corners": None if pd.isna(m.corners) else int(m.corners),
                        "band": None if pd.isna(m.band) else str(m.band),
                        "expected": num(m.expected, 3),
                        "cum_index": num(m.cum_index), "cum_lo": num(m.cum_lo),
                        "cum_hi": num(m.cum_hi),
                        "cum_cards_per_foul": num(m.cum_cards_per_foul, 4),
                    }
                    for m in matches.itertuples()
                ],
            }
        current_leagues[code] = {
            "league": code,
            "matches": int(len(group) // 2),
            "latest_date": str(group.Date.max())[:10],
            "yellows": ints(group.yellows), "fouls": ints(group.fouls), "reds": ints(group.reds),
            "cards_per_foul": cards_per_foul(group),
            "by_matchweek": by_matchweek_rates(group),
            "survive_bh": sorted(
                str(t) for t, r in clubs.items() if r["survives_bh"]),
            "clubs": clubs,
        }

    generated = datetime.now(UTC).isoformat(timespec="seconds")
    europe_by_matchweek = {
        str(k): quantile_rows(g.cum_index) for k, g in full_completed.groupby("n")
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "history").mkdir(exist_ok=True)
    (OUT / "meta.json").write_text(json.dumps({
        "generated_at": generated,
        "snapshot": snapshot.name,
        "snapshot_created_at": manifest["created_at"],
        "current_season": CURRENT_SEASON,
        "current_season_label": season_label(CURRENT_SEASON),
        "baseline_from": season_label(f"{BASELINE_FROM % 100:02d}{(BASELINE_FROM + 1) % 100:02d}"),
        "bands": {"edges": [None if math.isinf(b) else b for b in BANDS], "names": NAMES},
        "fdr": FDR,
        "complete_threshold": COMPLETE,
        "quantiles": QUANTILES,
        "leagues": leagues,
        "team_seasons_completed": int(full_completed.groupby(keys).ngroups),
        "history_from": season_label(min(completed.season)),
        "units": {"index": "yellow cards observed ÷ yellow cards expected",
                  "percentile": "% of clubs measured the same way at or below this index",
                  "cards_per_foul": "(yellow cards + red cards) ÷ fouls committed, as "
                                    "football-data records them. There is no second-yellow "
                                    "column: in England and Scotland a second-yellow dismissal "
                                    "is one red only, elsewhere one yellow and one red, so it "
                                    "counts twice. Yellows include dissent and bench cards, "
                                    "which have no foul under them."},
        "sources": SOURCES,
        "caveats": CAVEATS,
    }, indent=1, sort_keys=True) + "\n")
    (OUT / "current.json").write_text(json.dumps({
        "generated_at": generated,
        "snapshot": snapshot.name,
        "season": CURRENT_SEASON,
        "label": season_label(CURRENT_SEASON),
        "leagues": current_leagues,
        "europe_cum_index_by_matchweek": europe_by_matchweek,
        "europe_band_summary": band_summary(full_completed, europe_by_matchweek),
    }, separators=(",", ":"), sort_keys=True) + "\n")
    for code, payload in history_out.items():
        payload["generated_at"] = generated
        payload["snapshot"] = snapshot.name
        (OUT / "history" / f"{code}.json").write_text(
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")

    print(f"snapshot {snapshot.name}, {len(leagues)} leagues, "
          f"{int(club_now.shape[0])} clubs in {season_label(CURRENT_SEASON)}, "
          f"{int(full_completed.groupby(keys).ngroups):,} completed team-seasons")
    for code, info in leagues.items():
        m = info["model"]
        print(f"  {code:<4} {info['clubs_current']:>2} clubs, {info['matches_current']:>3} "
              f"matches to {info['latest_date']}, E = {m['intercept']:.4f} + "
              f"{m['slope']:.6f} x fouls")
    for path in sorted(OUT.rglob("*.json")):
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
