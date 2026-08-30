"""Separate club behaviour from referee assignment, where referees are named.

Portugal cannot answer this: a club booked more than its fouls and situation
predict might simply have drawn stricter officials. England and Scotland name
the referee on every match, so the two can be told apart.

Three expectations are built, each adding one adjustment:

    era            season league rate
    + situation    league-wide multiplier by odds-implied strength band
    + referee      that referee's own multiplier

The referee multiplier is estimated **excluding the club being tested**.
Otherwise a club that appears often with one official helps set the very
baseline it is judged against, and a real effect would partly cancel itself.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import COMPETITIONS, season_start_year
from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
pd.set_option("display.width", 240)

BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]
MIN_REF_MATCHES = 40
MIN_CLUB_MATCHES = 150


def ci(obs: float, exp: float) -> tuple[float, float]:
    lo = stats.chi2.ppf(0.025, 2 * obs) / 2 if obs > 0 else 0.0
    return lo / exp, stats.chi2.ppf(0.975, 2 * (obs + 1)) / 2 / exp


def prepare(directory: Path, code: str) -> pd.DataFrame:
    entries = [
        e for e in read_manifest(directory)
        if e.source == "football-data" and e.competition == code
    ]
    frame = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    tm = to_team_match(frame)
    tm["yr"] = tm["season"].map(season_start_year)
    tm = tm[tm["Referee"].notna() & (tm["Referee"].astype(str).str.len() > 1)]

    lg = tm.groupby("season", as_index=False).agg(
        f=("fouls", "sum"), y=("yellows", "sum"))
    lg["lg_ypf"] = lg.y / lg.f
    tm = tm.merge(lg[["season", "lg_ypf"]], on="season")
    tm["exp_era"] = tm.fouls * tm.lg_ypf

    tm["band"] = pd.cut(tm.strength_diff, BANDS, labels=NAMES)
    ctx = tm.groupby("band", observed=True, as_index=False).agg(
        y=("yellows", "sum"), e=("exp_era", "sum"))
    ctx["ctx_mult"] = ctx.y / ctx.e
    tm = tm.merge(ctx[["band", "ctx_mult"]], on="band", how="left")
    tm["ctx_mult"] = tm["ctx_mult"].fillna(1.0)
    tm["exp_ctx"] = tm.exp_era * tm.ctx_mult
    return tm


def analyse(tm: pd.DataFrame, label: str) -> pd.DataFrame:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(f"{len(tm):,} team-matches with a named referee, "
          f"{tm.Referee.nunique()} referees, {tm.yr.min()}-{tm.yr.max()}")

    refs = tm.groupby("Referee", as_index=False).agg(
        n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum"))
    busy = refs[refs.n >= MIN_REF_MATCHES].copy()
    busy["ref_mult"] = busy.y / busy.e
    print(f"\nreferees with {MIN_REF_MATCHES}+ team-matches: {len(busy)}")
    print(f"  their booking multiplier ranges {busy.ref_mult.min():.2f} to "
          f"{busy.ref_mult.max():.2f}  (median {busy.ref_mult.median():.2f})")
    spread = busy.ref_mult.max() - busy.ref_mult.min()
    print(f"  spread between officials: {spread:.2f}  "
          f"— for comparison the situation effect is about 0.27")

    rows = []
    for club, g in tm.groupby("team"):
        if len(g) < MIN_CLUB_MATCHES:
            continue
        # Referee multipliers estimated WITHOUT this club, to avoid a club
        # helping define the baseline it is measured against.
        others = tm[tm.team != club]
        rm = others.groupby("Referee", as_index=False).agg(
            n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum"))
        rm = rm[rm.n >= MIN_REF_MATCHES]
        rm["ref_mult"] = rm.y / rm.e
        merged = g.merge(rm[["Referee", "ref_mult"]], on="Referee", how="left")
        merged["ref_mult"] = merged["ref_mult"].fillna(1.0)
        merged["exp_ref"] = merged.exp_ctx * merged.ref_mult

        y = merged.yellows.sum()
        rows.append({
            "club": club, "n": len(merged), "yellows": int(y),
            "era": y / merged.exp_era.sum(),
            "situation": y / merged.exp_ctx.sum(),
            "referee": y / merged.exp_ref.sum(),
            "e_ctx": merged.exp_ctx.sum(), "e_ref": merged.exp_ref.sum(),
            "ref_draw": merged.ref_mult.mean(),
        })

    club = pd.DataFrame(rows)
    b_ctx = [ci(r.yellows, r.e_ctx) for r in club.itertuples()]
    b_ref = [ci(r.yellows, r.e_ref) for r in club.itertuples()]
    club["ctx_lo"], club["ctx_hi"] = [b[0] for b in b_ctx], [b[1] for b in b_ctx]
    club["ref_lo"], club["ref_hi"] = [b[0] for b in b_ref], [b[1] for b in b_ref]
    club["sep_situation"] = (club.ctx_lo > 1) | (club.ctx_hi < 1)
    club["sep_referee"] = (club.ref_lo > 1) | (club.ref_hi < 1)

    club = club.sort_values("referee")
    print(f"\n--- clubs with {MIN_CLUB_MATCHES}+ matches, booking index at each "
          "stage of adjustment ---")
    print(club[["club", "n", "era", "situation", "referee",
                "ref_lo", "ref_hi", "sep_situation", "sep_referee", "ref_draw"]]
          .round(3).to_string(index=False))

    n_ctx = int(club.sep_situation.sum())
    n_ref = int(club.sep_referee.sum())
    print(f"\nclubs separating after era + situation : {n_ctx} of {len(club)}")
    print(f"clubs separating after ALSO referee     : {n_ref} of {len(club)}")

    moved = club[club.sep_situation & ~club.sep_referee]
    if len(moved):
        print("\nEffect explained by REFEREE ASSIGNMENT (separated before, not after):")
        print(moved[["club", "situation", "referee", "ref_draw"]]
              .round(3).to_string(index=False))
    survivors = club[club.sep_referee]
    if len(survivors):
        print("\nEffect SURVIVES referee adjustment — a genuine club property:")
        print(survivors[["club", "n", "situation", "referee", "ref_lo", "ref_hi"]]
              .round(3).to_string(index=False))
    return club


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    for code in ("E0", "SC0"):
        comp = COMPETITIONS[code]
        analyse(prepare(directory, code), f"{comp.name} ({comp.country})")


if __name__ == "__main__":
    main()
