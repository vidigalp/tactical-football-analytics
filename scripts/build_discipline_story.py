"""Render the four discipline figures. Offline, from the committed snapshot."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import season_start_year
from tfa.ingest.matches import to_team_match
from tfa.managers import attach
from tfa.managers import load as load_managers
from tfa.metrics.discipline import team_season
from tfa.snapshot import read_manifest
from tfa.stats.shrinkage import beta_binomial_prior, shrink_beta_binomial
from tfa.viz import discipline_story as story
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]
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
    return frame


def main() -> None:
    theme.apply()
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    out = ROOT / "reports" / directory.name / "figures"
    stamp = directory.name
    written = []

    # ---------- Portuguese league, for figures 1-3 ----------
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
    written += story.clubs_before_after(club, out / "fig2-clubs-adjusted", snapshot=stamp)

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
    written += story.manager_travel(pairs, null, r, out / "fig3-manager-travel",
                                   snapshot=stamp)

    # ---------- shrinkage validation, all leagues ----------
    every = load_matches(directory)
    ts = team_season(every[every.year <= 2025])
    ts["yr"] = ts.season.map(season_start_year)
    ts = ts[ts.matches >= 30]
    parts = []
    for _, g in ts.groupby(["Div", "season"]):
        g = g.reset_index(drop=True)
        prior = beta_binomial_prior(g.yellows, g.fouls)
        est = shrink_beta_binomial(g.yellows, g.fouls, prior)
        g["raw"] = est["raw"].to_numpy()
        g["shrunk"] = est["shrunk"].to_numpy()
        g["league_mean"] = prior.mean
        parts.append(g)
    ts = pd.concat(parts, ignore_index=True)
    nxt = ts[["Div", "team", "yr", "yellows", "fouls"]].copy()
    nxt["yr"] -= 1
    nxt = nxt.rename(columns={"yellows": "y_next", "fouls": "f_next"})
    p = ts.merge(nxt, on=["Div", "team", "yr"])
    p["actual"] = p.y_next / p.f_next
    scores = {
        "raw ratio": float(np.sqrt(np.mean((p["raw"] - p.actual) ** 2))),
        "shrunken estimate": float(np.sqrt(np.mean((p["shrunk"] - p.actual) ** 2))),
        "ignore the club,\nuse the league mean":
            float(np.sqrt(np.mean((p.league_mean - p.actual) ** 2))),
    }
    written += story.shrinkage_validation(scores, out / "fig4-shrinkage-validation",
                                          n_pairs=len(p), snapshot=stamp)

    for w in written:
        print("wrote", w.relative_to(ROOT))
    print(f"\ncontext swing: {100 * (ctx.multiplier.iloc[0] / ctx.multiplier.iloc[-1] - 1):.0f}%")
    print(f"clubs separating after adjustment: "
          f"{int(((club.lo > 1) | (club.hi < 1)).sum())} of {len(club)}")
    print(f"manager travel r = {r:+.3f}, permutation p = "
          f"{float(np.mean(np.abs(null) >= abs(r))):.3f}")


if __name__ == "__main__":
    main()
