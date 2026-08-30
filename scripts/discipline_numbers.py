"""Every number published in study 02, computed from the committed snapshot.

Written after a meta-analysis found two errors in the first version of that
study, both traceable to one cause: figures came from a correctly-scoped script,
but several numbers in the prose came from ad-hoc analysis that was never
committed. One of them had the wrong sign and inverted the conclusion.

So this script owns the numbers. It writes `numbers.json` next to the report,
and the report quotes nothing that is not in that file.

Run: uv run python scripts/discipline_numbers.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]

#: The study these numbers belong to. The snapshot it reads is dated earlier —
#: data is pulled before the report is written, which is the point.
REPORT = "2026-W36"

#: Pre-match role, from the devigged odds. Symmetric about zero by construction.
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]


def load(snapshot: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(snapshot.glob("football-data__*.parquet")):
        frame = pd.read_parquet(path)
        if "strength_diff" not in frame:
            continue
        frame = frame.dropna(subset=["HF", "AF", "HY", "AY", "strength_diff"])
        frames.append(frame.assign(lg=path.name.split("__")[1]))
    return pd.concat(frames, ignore_index=True)


def team_rows(matches: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match, carrying the opponent's counts alongside.

    strength_diff is log(p_home/p_away), so it flips sign for the away side.
    """
    home = pd.DataFrame({
        "lg": matches.lg, "season": matches.season,
        "team": matches.HomeTeam, "opp": matches.AwayTeam,
        "f": matches.HF, "y": matches.HY, "of": matches.AF, "oy": matches.AY,
        "s": matches.strength_diff,
    })
    away = pd.DataFrame({
        "lg": matches.lg, "season": matches.season,
        "team": matches.AwayTeam, "opp": matches.HomeTeam,
        "f": matches.AF, "y": matches.AY, "of": matches.HF, "oy": matches.HY,
        "s": -matches.strength_diff,
    })
    return pd.concat([home, away], ignore_index=True)


def context_by_league(teams: pd.DataFrame) -> pd.DataFrame:
    """Booking index by pre-match role, per league. Never pooled: Phatak et al.
    (2021) document Simpson's paradox on exactly this ratio."""
    teams = teams.assign(role=pd.cut(teams.s, BANDS, labels=NAMES))
    out = []
    for lg, group in teams.groupby("lg"):
        rate = group.y.sum() / group.f.sum()
        row = group.groupby("role", observed=True).apply(
            lambda g, r=rate: g.y.sum() / (r * g.f.sum()), include_groups=False)
        out.append({"lg": lg, **row.to_dict()})
    return pd.DataFrame(out).set_index("lg")


def own_and_opponent(teams: pd.DataFrame) -> pd.DataFrame:
    """Does a club's strength predict its own booking index, and its opponents'?

    These two carry the conclusion. The first version of the study published the
    own correlation as +0.486; it is negative in every league, which is what the
    study's own opening number (a strong club at 0.884) already implied.
    """
    out = []
    for lg, group in teams.groupby("lg"):
        rate = group.y.sum() / group.f.sum()
        cs = group.groupby(["season", "team"]).agg(
            f=("f", "sum"), y=("y", "sum"), of=("of", "sum"), oy=("oy", "sum"),
            s=("s", "mean"))
        cs = cs[(cs.f > 0) & (cs.of > 0)]
        out.append({
            "lg": lg, "n": len(cs),
            "own": stats.spearmanr(cs.s, cs.y / (rate * cs.f)).statistic,
            "opp": stats.spearmanr(cs.s, cs.oy / (rate * cs.of)).statistic,
        })
    return pd.DataFrame(out).set_index("lg")


def within_club(teams: pd.DataFrame) -> tuple[pd.DataFrame, float, int]:
    """Hold the club fixed; split its matches by opponent quality.

    The cleanest evidence that this is situational rather than a club property,
    because club identity is differenced out.
    """
    opp_quality = teams.groupby(["lg", "season", "team"])["s"].mean().rename("oq")
    teams = teams.merge(opp_quality, left_on=["lg", "season", "opp"], right_index=True)

    rows = []
    for lg, group in teams.groupby("lg"):
        rate = group.y.sum() / group.f.sum()
        group = group.assign(tercile=group.groupby("season")["oq"].transform(
            lambda s: pd.qcut(s, 3, labels=["weak", "mid", "strong"], duplicates="drop")))
        row = group.groupby("tercile", observed=True).apply(
            lambda g, r=rate: g.y.sum() / (r * g.f.sum()), include_groups=False)
        rows.append({"lg": lg, **row.to_dict()})

    hits = total = 0
    for (lg, _team), group in teams.groupby(["lg", "team"]):
        if len(group) < 60:
            continue
        league = teams[teams.lg == lg]
        rate = league.y.sum() / league.f.sum()
        median = group.oq.median()
        low, high = group[group.oq <= median], group[group.oq > median]
        if low.f.sum() == 0 or high.f.sum() == 0:
            continue
        total += 1
        if high.y.sum() / (rate * high.f.sum()) > low.y.sum() / (rate * low.f.sum()):
            hits += 1
    return pd.DataFrame(rows).set_index("lg"), hits / total, total


def match_level(matches: pd.DataFrame) -> pd.DataFrame:
    """Does the match TOTAL scale with fixture quality?

    The first version concluded cards per foul rise with fixture quality "for
    both teams", which predicts exactly this. It does not happen: the favourite's
    fall and the underdog's rise cancel on aggregation.
    """
    out = []
    for lg, group in matches.groupby("lg"):
        group = group.copy()
        group["fouls"] = group.HF + group.AF
        group["cards"] = group.HY + group.AY
        slope, intercept = np.polyfit(group.fouls, group.cards, 1)
        group["idx"] = group.cards / (intercept + slope * group.fouls)
        strength = pd.concat([
            pd.DataFrame({"season": group.season, "team": group.HomeTeam,
                          "s": group.strength_diff}),
            pd.DataFrame({"season": group.season, "team": group.AwayTeam,
                          "s": -group.strength_diff}),
        ]).groupby(["season", "team"])["s"].mean().rename("q")
        group = (group.merge(strength, left_on=["season", "HomeTeam"], right_index=True)
                      .merge(strength, left_on=["season", "AwayTeam"],
                             right_index=True, suffixes=("_h", "_a")))
        quality = (group.q_h + group.q_a) / 2
        out.append({"lg": lg, "r": stats.spearmanr(quality, group.idx).statistic})
    return pd.DataFrame(out).set_index("lg")


def affine_adequacy(matches: pd.DataFrame) -> dict:
    """Is a straight line enough, or would curvature masquerade as a gradient?"""
    fouls = matches.HF + matches.AF
    cards = matches.HY + matches.AY
    lin = np.polyval(np.polyfit(fouls, cards, 1), fouls)
    quad = np.polyval(np.polyfit(fouls, cards, 2), fouls)
    rmse_l = float(np.sqrt(((cards - lin) ** 2).mean()))
    rmse_q = float(np.sqrt(((cards - quad) ** 2).mean()))
    return {"rmse_linear": rmse_l, "rmse_quadratic": rmse_q,
            "improvement_pct": 100 * (1 - rmse_q / rmse_l)}


def portugal_clubs(teams: pd.DataFrame) -> dict:
    p1 = teams[teams.lg == "P1"]
    rate = p1.y.sum() / p1.f.sum()
    club = p1.groupby("team").agg(f=("f", "sum"), y=("y", "sum"))
    club = club[club.f > 500]
    return {t: round(float(r.y / (rate * r.f)), 3) for t, r in club.iterrows()}


def main() -> None:
    snapshot = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    matches = load(snapshot)
    teams = team_rows(matches)

    ctx = context_by_league(teams)
    corr = own_and_opponent(teams)
    ter, share, n_clubs = within_club(teams)
    ml = match_level(matches)

    numbers = {
        "snapshot": snapshot.name,
        "matches": int(len(matches)),
        "leagues": int(matches.lg.nunique()),
        "context": {
            "by_league": ctx.round(3).to_dict(orient="index"),
            "median_heavy_underdog": round(float(ctx["heavy underdog"].median()), 3),
            "median_heavy_favourite": round(float(ctx["heavy favourite"].median()), 3),
            "monotone_leagues": int(sum(
                ctx.loc[lg].is_monotonic_decreasing for lg in ctx.index)),
        },
        "correlations": {
            "by_league": corr.round(3).to_dict(orient="index"),
            "median_own": round(float(corr.own.median()), 3),
            "median_opp": round(float(corr.opp.median()), 3),
            "own_negative_leagues": int((corr.own < 0).sum()),
            "opp_positive_leagues": int((corr.opp > 0).sum()),
        },
        "within_club": {
            "by_league": ter.round(3).to_dict(orient="index"),
            "median_weak": round(float(ter.weak.median()), 3),
            "median_strong": round(float(ter.strong.median()), 3),
            "strong_above_weak_leagues": int((ter.strong > ter.weak).sum()),
            "club_share": round(share, 3),
            "clubs_tested": n_clubs,
        },
        "match_level": {
            "by_league": ml.round(3).to_dict(orient="index"),
            "median_r": round(float(ml.r.median()), 3),
        },
        "affine": affine_adequacy(matches),
        "portugal_raw_index": portugal_clubs(teams),
    }

    out = ROOT / "reports" / REPORT / "numbers.json"
    out.write_text(json.dumps(numbers, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    c = numbers["correlations"]
    print(f"  own  median {c['median_own']:+.3f}  negative in {c['own_negative_leagues']}/11")
    print(f"  opp  median {c['median_opp']:+.3f}  positive in {c['opp_positive_leagues']}/11")
    print(f"  match level median r {numbers['match_level']['median_r']:+.3f}")


if __name__ == "__main__":
    main()
