"""Render study 02's figures and write the numerals they carry. Offline.

Every value this script puts on a figure also goes into ``story.json``, so a
number in the report can be traced to a committed artifact rather than to a
figure stamp. Two numerals reached the published page through a stamp alone —
the 2,432 club-season pairs behind the shrinkage validation and the 13% by which
shrinking beats the raw ratio — and a stamp is not readable by a test.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import is_completed, season_start_year
from tfa.ingest.matches import to_team_match
from tfa.managers import attach
from tfa.managers import load as load_managers
from tfa.snapshot import read_manifest
from tfa.viz import discipline_story as story
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]

#: The study these figures belong to.
REPORT = "02-fouling-with-impunity"
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy\nunderdog", "underdog", "even", "favourite", "heavy\nfavourite"]


def ci(obs: float, exp: float) -> tuple[float, float]:
    lo = stats.chi2.ppf(0.025, 2 * obs) / 2 if obs > 0 else 0.0
    return lo / exp, stats.chi2.ppf(0.975, 2 * (obs + 1)) / 2 / exp


def load_matches(directory: Path, comp: str | None = None) -> pd.DataFrame:
    entries = [
        e for e in read_manifest(directory)
        if e.source == "football-data" and (comp is None or e.competition == comp)
    ]
    frame = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    frame["year"] = frame["season"].map(season_start_year)
    # Retrospective throughout this script. Previously only the shrinkage block
    # filtered, so the Portuguese figures and the club table were fitted on ten
    # seasons plus four matchweeks of the season being investigated, while the
    # shrinkage validation was fitted on ten. One study, two windows.
    return frame[frame["season"].map(is_completed)]


def main() -> None:
    theme.apply()
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    # The report is dated later than the snapshot it reads, so the output
    # directory cannot be derived from the snapshot name. Writing there put
    # study 02's figures in study 01's folder and left study 02's untouched.
    out = ROOT / "reports" / REPORT / "figures"
    stamp = directory.name
    written = []

    # ---------- Portuguese league: context, manager travel, club table ----------
    tm = to_team_match(load_matches(directory, "P1"))
    lg = tm.groupby("season", as_index=False).agg(
        f=("fouls", "sum"), y=("yellows", "sum"))
    lg["lg_ypf"] = lg.y / lg.f
    tm = tm.merge(lg[["season", "lg_ypf"]], on="season")
    tm["exp_era"] = tm.fouls * tm.lg_ypf
    tm["band"] = pd.cut(tm.strength_diff, BANDS, labels=NAMES)

    ctx = tm.groupby("band", observed=True, as_index=False).agg(
        y=("yellows", "sum"), e=("exp_era", "sum"), n=("fouls", "size"))
    ctx["multiplier"] = ctx.y / ctx.e
    bounds = [ci(y, e) for y, e in zip(ctx.y, ctx.e, strict=True)]
    ctx["lo"], ctx["hi"] = [b[0] for b in bounds], [b[1] for b in bounds]
    written += story.context_effect(ctx, out / "fig1-context-effect", snapshot=stamp)

    # The same gradient across every division, so the Portugal figure above
    # cannot be read as a quirk of one league. Names are scoped to this block:
    # `tm` and `rows` below belong to the Portuguese figures and reassigning
    # them here silently emptied the club table and manager-travel figures.
    def league_profile(directory: Path) -> pd.DataFrame:
        per_league = []
        for code, group in load_matches(directory).groupby("Div"):
            side = to_team_match(group)
            era = side.groupby("season", as_index=False).agg(
                f=("fouls", "sum"), y=("yellows", "sum"))
            era["lg_ypf"] = era.y / era.f
            side = side.merge(era[["season", "lg_ypf"]], on="season")
            side["exp_era"] = side.fouls * side.lg_ypf
            side["band"] = pd.cut(side.strength_diff, BANDS, labels=NAMES)
            per_league.append(
                side.groupby("band", observed=True)
                .apply(lambda g: g.yellows.sum() / g.exp_era.sum(), include_groups=False)
                .rename(code)
            )
        return pd.DataFrame(per_league).reindex(columns=NAMES).dropna()

    profile = league_profile(directory)
    written += story.context_all_leagues(
        profile, out / "fig2-context-all-leagues", snapshot=stamp)

    def yellows_per_foul_curve(directory: Path) -> pd.DataFrame:
        """Observed yellows per foul against the team's foul count in that match."""
        side = to_team_match(load_matches(directory))
        band = pd.cut(side.fouls, [0, 6, 8, 10, 12, 14, 16, 18, 20, 40],
                      include_lowest=True)
        grouped = side.groupby(band, observed=True).agg(
            fouls=("fouls", "mean"), n=("fouls", "size"),
            cards=("yellows", "sum"), total=("fouls", "sum"))
        grouped = grouped[grouped.n >= 200]
        grouped["rate"] = grouped.cards / grouped.total
        lo, hi = [], []
        for cards, total in zip(grouped.cards, grouped.total, strict=True):
            bounds = ci(cards, total)
            lo.append(bounds[0])
            hi.append(bounds[1])
        grouped["lo"], grouped["hi"] = lo, hi
        grouped["weight"] = grouped.total
        return grouped.reset_index(drop=True)

    written += story.yellows_per_foul(
        yellows_per_foul_curve(directory), out / "fig3-yellows-per-foul", snapshot=stamp)

    def opponent_terciles(directory: Path) -> pd.DataFrame:
        """A club's own index, split by the strength of who it faced."""
        per_league = []
        for code, group in load_matches(directory).groupby("Div"):
            side = to_team_match(group)
            era = side.groupby("season", as_index=False).agg(
                f=("fouls", "sum"), y=("yellows", "sum"))
            era["lg_ypf"] = era.y / era.f
            side = side.merge(era[["season", "lg_ypf"]], on="season")
            side["exp_era"] = side.fouls * side.lg_ypf
            # Opponent quality is the opponent's own season strength, so the
            # split is about who they played and not about that one match.
            quality = side.groupby(["season", "team"])["strength_diff"].mean().rename("oq")
            side = side.merge(quality, left_on=["season", "opponent"], right_index=True)
            side["tercile"] = side.groupby("season")["oq"].transform(
                lambda s: pd.qcut(s, 3, labels=["weak", "mid", "strong"], duplicates="drop"))
            row = side.groupby("tercile", observed=True).apply(
                lambda g: g.yellows.sum() / g.exp_era.sum(), include_groups=False)
            per_league.append(row.rename(code))
        return pd.DataFrame(per_league).reindex(
            columns=["weak", "mid", "strong"]).dropna()

    terciles = opponent_terciles(directory)
    written += story.opponent_test(
        terciles, out / "fig4-opponent-test", snapshot=stamp)

    tm = tm.merge(ctx[["band", "multiplier"]], on="band", how="left")
    tm["expected"] = tm.exp_era * tm.multiplier.fillna(1.0)

    club = tm.groupby("team", as_index=False).agg(
        n=("fouls", "size"), y=("yellows", "sum"),
        e_era=("exp_era", "sum"), e_adj=("expected", "sum"))
    club = club[club.n >= 80].copy()
    club["raw"] = club.y / club.e_era
    club["adjusted"] = club.y / club.e_adj
    bounds = [ci(y, e) for y, e in zip(club.y, club.e_adj, strict=True)]
    club["lo"], club["hi"] = [b[0] for b in bounds], [b[1] for b in bounds]
    written += story.clubs_before_after(club, out / "fig6-clubs-adjusted", snapshot=stamp)

    # ---------- manager travel ----------
    known = attach(tm, load_managers("primeira_liga"))
    known = known[known.manager.notna()]
    spell = known.groupby(["manager", "team"], as_index=False).agg(
        n=("fouls", "size"), y=("yellows", "sum"), e=("expected", "sum"),
        first=("Date", "min"))
    spell = spell[spell.n >= 15]
    rows = []
    for _, s in spell.iterrows():
        rest = known[(known.team == s.team) & (known.manager != s.manager)]
        if rest.yellows.sum() < 30:
            continue
        base = rest.yellows.sum() / rest.expected.sum()
        rows.append({**s.to_dict(), "vs_club": (s.y / s.e) / base})
    spell = pd.DataFrame(rows)

    multi = spell.groupby("manager").filter(lambda g: g.team.nunique() >= 2)
    pairs = []
    for mgr, g in multi.groupby("manager"):
        g = g.sort_values("first")
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if g.iloc[i].team != g.iloc[j].team:
                    pairs.append({"manager": mgr, "a": g.iloc[i].vs_club,
                                  "b": g.iloc[j].vs_club})
    pairs = pd.DataFrame(pairs)
    r = float(stats.pearsonr(pairs.a, pairs.b)[0])
    rng = np.random.default_rng(20260829)
    null = np.array([
        stats.pearsonr(pairs.a, rng.permutation(pairs.b.to_numpy()))[0]
        for _ in range(5000)
    ])
    written += story.manager_travel(pairs, null, r, out / "fig5-manager-travel",
                                   snapshot=stamp)

    for w in written:
        print("wrote", w.relative_to(ROOT))

    separating = int(((club.lo > 1) | (club.hi < 1)).sum())
    swing = float(ctx.multiplier.iloc[0] / ctx.multiplier.iloc[-1] - 1)
    permutation_p = float(np.mean(np.abs(null) >= abs(r)))
    cpf = yellows_per_foul_curve(directory)

    facts = {
        "snapshot": stamp,
        "situation": {
            "bands": {
                str(name).replace("\n", " "): float(mult)
                for name, mult in zip(ctx.band, ctx.multiplier, strict=True)
            },
            "swing_underdog_over_favourite": swing,
        },
        "clubs": {
            "n_ranked": int(len(club)),
            "min_matches": 80,
            "separating_after_adjustment": separating,
            "index": {
                row.team: {"raw": float(row.raw), "adjusted": float(row.adjusted),
                           "lo": float(row.lo), "hi": float(row.hi)}
                for row in club.itertuples()
            },
        },
        "manager_travel": {
            "pairs": int(len(pairs)),
            "r": r,
            "permutation_p": permutation_p,
            "permutations": 5000,
        },
        "yellows_per_foul": {
            f"{row.fouls:.1f}": float(row.rate) for row in cpf.itertuples()
        },
        "all_leagues": {
            "n": int(len(profile)),
            "median_heavy_underdog": float(profile[NAMES[0]].median()),
            "median_heavy_favourite": float(profile[NAMES[-1]].median()),
            "underdog_end_above_favourite_end": int(
                (profile[NAMES[0]] > profile[NAMES[-1]]).sum()
            ),
            # Strictly decreasing from the underdog band to the favourite band.
            # The report distinguishes "the direction is everywhere" from "the
            # staircase is clean", and only the second of those is a count.
            "strictly_monotone": int(
                profile.apply(
                    lambda row: bool(
                        all(a > b for a, b in zip(row[:-1], row[1:], strict=True))
                    ),
                    axis=1,
                ).sum()
            ),
            "by_league": {
                str(code): {str(k).replace("\n", " "): float(v) for k, v in row.items()}
                for code, row in profile.iterrows()
            },
        },
        "opponent_terciles": {
            "portugal": {
                str(k): float(v) for k, v in terciles.loc["P1"].items()
            },
            "median_of_leagues": {
                str(k): float(v) for k, v in terciles.median().items()
            },
            "rising_in": int((terciles.strong > terciles.weak).sum()),
            "leagues": int(len(terciles)),
        },
    }
    sidecar = ROOT / "reports" / REPORT / "story.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"wrote {sidecar.relative_to(ROOT)}")

    print(f"\ncontext swing: {100 * swing:.0f}%")
    print(f"clubs separating after adjustment: {separating} of {len(club)}")
    print(f"manager travel r = {r:+.3f}, permutation p = {permutation_p:.3f}")



if __name__ == "__main__":
    main()
