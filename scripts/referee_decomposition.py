"""Separate club behaviour from referee assignment across England, Scotland and Portugal.

England and Scotland name the referee on every match in football-data.co.uk;
Portugal's officials come from data/managers/primeira_liga_referees.csv,
harvested from zerozero.pt and joined on scorelines.

Three expectations are built, each adding one adjustment:

    era            season league rate
    + situation    league-wide multiplier by odds-implied strength band
    + referee      that referee's own multiplier

The referee multiplier is estimated **excluding the club being tested**.
Otherwise a club that appears often with one official helps set the very
baseline it is judged against, and a real effect would partly cancel itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import COMPETITIONS, is_completed, season_start_year
from tfa.ingest.matches import to_team_match
from tfa.ingest.referees import join_to_matches
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"
pd.set_option("display.width", 240)

BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]
MIN_REF_MATCHES = 40
MIN_CLUB_MATCHES = 150
LEAGUE_MIN_CLUB_MATCHES = {"E0": 150, "SC0": 150, "P1": 80}


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
    frame = frame[frame["season"].map(is_completed)]
    if code == "P1":
        frame = frame.dropna(subset=["HF", "AF", "HY", "AY", "strength_diff"]).copy()
        refs_csv = pd.read_csv(ROOT / "data" / "managers" / "primeira_liga_referees.csv")
        joined, _ = join_to_matches(refs_csv, frame)
        home = pd.DataFrame({
            "season": joined.season, "team": joined.HomeTeam, "opponent": joined.AwayTeam,
            "fouls": joined.HF, "yellows": joined.HY,
            "strength_diff": joined.strength_diff, "Referee": joined.referee,
        })
        away = pd.DataFrame({
            "season": joined.season, "team": joined.AwayTeam, "opponent": joined.HomeTeam,
            "fouls": joined.AF, "yellows": joined.AY,
            "strength_diff": -joined.strength_diff, "Referee": joined.referee,
        })
        tm = pd.concat([home, away], ignore_index=True)
        tm["yr"] = tm["season"].map(season_start_year)
    else:
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
    tm["ctx_mult"] = tm["ctx_mult"].astype(float).fillna(1.0)
    tm["exp_ctx"] = tm.exp_era * tm.ctx_mult
    return tm


def analyse(tm: pd.DataFrame, label: str, min_club_matches: int = MIN_CLUB_MATCHES) -> pd.DataFrame:
    known = tm[tm["Referee"].notna()]
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(f"{len(tm):,} team-matches ({known.Referee.nunique()} referees), "
          f"{tm.yr.min()}-{tm.yr.max()}")

    refs = known.groupby("Referee", as_index=False).agg(
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
        if len(g) < min_club_matches:
            continue
        # Referee multipliers estimated WITHOUT this club, to avoid a club
        # helping define the baseline it is measured against.
        others = known[known.team != club]
        rm = others.groupby("Referee", as_index=False).agg(
            n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum"))
        rm = rm[rm.n >= MIN_REF_MATCHES].copy()
        rm["ref_mult"] = rm.y / rm.e
        mult_map = rm.set_index("Referee")["ref_mult"]
        mult = g["Referee"].map(mult_map)
        exp_ref = (g["exp_ctx"] * mult.fillna(1.0)).sum()

        y = g.yellows.sum()
        rows.append({
            "club": str(club), "n": int(len(g)), "yellows": int(y),
            "era": float(y / g.exp_era.sum()),
            "situation": float(y / g.exp_ctx.sum()),
            "referee": float(y / exp_ref),
            "e_ctx": float(g.exp_ctx.sum()), "e_ref": float(exp_ref),
            "ref_draw": float(mult.mean()),
        })

    club = pd.DataFrame(rows)
    b_ctx = [ci(r.yellows, r.e_ctx) for r in club.itertuples()]
    b_ref = [ci(r.yellows, r.e_ref) for r in club.itertuples()]
    club["ctx_lo"], club["ctx_hi"] = [b[0] for b in b_ctx], [b[1] for b in b_ctx]
    club["ref_lo"], club["ref_hi"] = [b[0] for b in b_ref], [b[1] for b in b_ref]
    club["sep_situation"] = (club.ctx_lo > 1) | (club.ctx_hi < 1)
    club["sep_referee"] = (club.ref_lo > 1) | (club.ref_hi < 1)

    club = club.sort_values("referee")
    print(f"\n--- clubs with {min_club_matches}+ matches, booking index at each "
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
    facts: dict = {"snapshot": directory.name, "leagues": {}}
    all_clubs = []
    total_tm = 0
    total_refs = 0
    total_busy = 0

    for code in ("E0", "SC0", "P1"):
        comp = COMPETITIONS[code]
        min_club_m = LEAGUE_MIN_CLUB_MATCHES[code]
        tm = prepare(directory, code)
        club = analyse(tm, f"{comp.name} ({comp.country})", min_club_m)
        club["league"] = code
        all_clubs.append(club)

        known = tm[tm["Referee"].notna()]
        refs = known.groupby("Referee", as_index=False).agg(
            n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum"))
        busy = refs[refs.n >= MIN_REF_MATCHES]
        multiplier = busy.y / busy.e

        total_tm += int(len(tm))
        total_refs += int(known.Referee.nunique())
        total_busy += int(len(multiplier))

        facts["leagues"][code] = {
            "country": comp.country,
            "team_matches": int(len(tm)),
            "referees": int(known.Referee.nunique()),
            "officials_over_threshold": int(len(multiplier)),
            "min_referee_matches": MIN_REF_MATCHES,
            "min_club_matches": min_club_m,
            "multiplier_min": float(multiplier.min()),
            "multiplier_max": float(multiplier.max()),
            "multiplier_median": float(multiplier.median()),
            "multiplier_spread": float(multiplier.max() - multiplier.min()),
            "clubs": int(len(club)),
            "ref_draw_min": float(club.ref_draw.min()),
            "ref_draw_max": float(club.ref_draw.max()),
            "rms_ref_shift": float(np.sqrt(np.mean((club.referee - club.situation) ** 2))),
            "separating_after_situation": int(club.sep_situation.sum()),
            "separating_after_referee": int(club.sep_referee.sum()),
        }

    pooled = pd.concat(all_clubs, ignore_index=True)
    facts["total_team_matches"] = total_tm
    facts["total_referees"] = total_refs
    facts["total_officials_over_threshold"] = total_busy
    facts["total_clubs"] = int(len(pooled))
    facts["overall_ref_draw_min"] = float(pooled.ref_draw.min())
    facts["overall_ref_draw_max"] = float(pooled.ref_draw.max())
    facts["overall_rms_ref_shift"] = float(
        np.sqrt(np.mean((pooled.referee - pooled.situation) ** 2))
    )
    facts["overall_max_ref_shift"] = float((pooled.referee - pooled.situation).abs().max())
    facts["overall_corr_sit_ref"] = float(stats.pearsonr(pooled.situation, pooled.referee)[0])
    facts["clubs"] = pooled.to_dict(orient="records")

    sidecar = ROOT / "reports" / REPORT / "referee_decomposition.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {sidecar.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
