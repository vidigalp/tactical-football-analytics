"""Compute comprehensive Pan-European universe statistics across all 11 leagues.

Produces `paper/universe_results.json` from committed snapshots in `data/snapshots/2026-W36/`
and `data/managers/primeira_liga_referees.csv`.
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
from tfa.metrics.discipline import team_season
from tfa.snapshot import read_manifest
from tfa.stats.shrinkage import beta_binomial_prior, shrink_beta_binomial

ROOT = Path(__file__).resolve().parents[1]
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]
MIN_REF_MATCHES = 40


def poisson_ci(obs: float, exp: float) -> tuple[float, float]:
    lo = stats.chi2.ppf(0.025, 2 * obs) / 2 if obs > 0 else 0.0
    hi = stats.chi2.ppf(0.975, 2 * (obs + 1)) / 2
    return float(lo / exp), float(hi / exp)


def poisson_two_sided(observed: int, expected: float) -> float:
    if expected <= 0:
        return 1.0
    if observed >= expected:
        tail = stats.poisson.sf(observed - 1, expected)
    else:
        tail = stats.poisson.cdf(observed, expected)
    return float(min(1.0, 2 * tail))


def bh_adjust(p_values: np.ndarray) -> np.ndarray:
    m = len(p_values)
    if m == 0:
        return np.array([])
    order = np.argsort(p_values)
    ranked = p_values[order]
    adjusted = np.minimum.accumulate(
        (ranked * m / np.arange(1, m + 1))[::-1]
    )[::-1].clip(max=1.0)
    out = np.empty(m)
    out[order] = adjusted
    return out


def fit_quartic_poisson(s: np.ndarray, y: np.ndarray, base_exp: np.ndarray, degree: int = 4) -> np.ndarray:
    X = np.column_stack([s**k for k in range(degree + 1)])
    offset = np.log(np.maximum(base_exp, 1e-9))
    beta = np.zeros(X.shape[1])
    for _ in range(80):
        mu = np.exp(np.clip(X @ beta + offset, -20, 20))
        w = np.maximum(mu, 1e-9)
        z = X @ beta + (y - mu) / w
        step = np.linalg.solve(X.T @ (X * w[:, None]) + 1e-9 * np.eye(X.shape[1]), X.T @ (w * z))
        if np.max(np.abs(step - beta)) < 1e-10:
            beta = step
            break
        beta = step
    return np.exp(np.clip(X @ beta + offset, -20, 20))


def fit_fixture_poisson(
    s_diff: np.ndarray,
    s_own: np.ndarray,
    s_opp: np.ndarray,
    y: np.ndarray,
    base_exp: np.ndarray,
) -> np.ndarray:
    """Adjust for match strength difference (degree 4) plus fixture/club quality."""
    X = np.column_stack([
        np.ones(len(s_diff)),
        s_diff,
        s_diff**2,
        s_diff**3,
        s_diff**4,
        s_own,
        s_opp,
    ])
    offset = np.log(np.maximum(base_exp, 1e-9))
    beta = np.zeros(X.shape[1])
    for _ in range(80):
        mu = np.exp(np.clip(X @ beta + offset, -20, 20))
        w = np.maximum(mu, 1e-9)
        z = X @ beta + (y - mu) / w
        step = np.linalg.solve(X.T @ (X * w[:, None]) + 1e-9 * np.eye(X.shape[1]), X.T @ (w * z))
        if np.max(np.abs(step - beta)) < 1e-10:
            beta = step
            break
        beta = step
    return np.exp(np.clip(X @ beta + offset, -20, 20))


def load_completed_team_matches(directory: Path) -> pd.DataFrame:
    frames = []
    for code in COMPETITIONS:
        entries = [
            e for e in read_manifest(directory)
            if e.source == "football-data" and e.competition == code
        ]
        if not entries:
            continue
        frame = pd.concat(
            [pd.read_parquet(directory / e.parquet_path) for e in entries],
            ignore_index=True,
        )
        frame = frame[frame["season"].map(is_completed)]
        if code == "P1":
            refs = pd.read_csv(ROOT / "data" / "managers" / "primeira_liga_referees.csv")
            valid = frame.dropna(subset=["HF", "AF", "HY", "AY", "strength_diff"]).copy()
            joined, _ = join_to_matches(refs, valid)
            joined["Referee"] = joined["referee"]
            frame = joined
        tm = to_team_match(frame)
        tm["league"] = code
        frames.append(tm)
    tm = pd.concat(frames, ignore_index=True)
    tm = tm.dropna(subset=["strength_diff", "fouls", "yellows"]).copy()
    tm["yr"] = tm["season"].map(season_start_year)
    return tm


def run_referee_decomposition(directory: Path) -> dict:
    """Leave-one-club-out referee decomposition across E0, SC0, and P1."""
    ref_results = {}
    all_club_rows = []
    total_tm = 0
    total_refs = 0
    total_refs_40 = 0

    for code, min_club_m in [("E0", 150), ("SC0", 150), ("P1", 80)]:
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
        else:
            tm = to_team_match(frame)
            tm = tm[tm["Referee"].notna() & (tm["Referee"].astype(str).str.len() > 1)].copy()

        lg = tm.groupby("season", as_index=False).agg(f=("fouls", "sum"), y=("yellows", "sum"))
        lg["lg_ypf"] = lg.y / lg.f
        tm = tm.merge(lg[["season", "lg_ypf"]], on="season")
        tm["exp_era"] = tm.fouls * tm.lg_ypf

        tm["band"] = pd.cut(tm.strength_diff, BANDS, labels=NAMES)
        ctx = tm.groupby("band", observed=True, as_index=False).agg(
            y=("yellows", "sum"), e=("exp_era", "sum")
        )
        ctx["ctx_mult"] = ctx.y / ctx.e
        tm = tm.merge(ctx[["band", "ctx_mult"]], on="band", how="left")
        tm["ctx_mult"] = tm["ctx_mult"].astype(float).fillna(1.0)
        tm["exp_ctx"] = tm.exp_era * tm.ctx_mult

        known_refs = tm[tm["Referee"].notna()]
        ref_agg = known_refs.groupby("Referee", as_index=False).agg(
            n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum")
        )
        busy = ref_agg[ref_agg.n >= MIN_REF_MATCHES].copy()
        busy["ref_mult"] = busy.y / busy.e

        rows = []
        for club, g in tm.groupby("team"):
            if len(g) < min_club_m:
                continue
            others = known_refs[known_refs.team != club]
            rm = others.groupby("Referee", as_index=False).agg(
                n=("fouls", "size"), y=("yellows", "sum"), e=("exp_ctx", "sum")
            )
            rm = rm[rm.n >= MIN_REF_MATCHES].copy()
            rm["ref_mult"] = rm.y / rm.e
            mult_map = rm.set_index("Referee")["ref_mult"]
            mult = g["Referee"].map(mult_map)
            exp_ref = (g["exp_ctx"] * mult.fillna(1.0)).sum()
            y_sum = int(g["yellows"].sum())
            e_era = float(g["exp_era"].sum())
            e_ctx = float(g["exp_ctx"].sum())
            lo_ctx, hi_ctx = poisson_ci(y_sum, e_ctx)
            lo_ref, hi_ref = poisson_ci(y_sum, exp_ref)
            rows.append({
                "league": code,
                "club": str(club),
                "n": int(len(g)),
                "fouls": int(g["fouls"].sum()),
                "yellows": y_sum,
                "strength": float(g["strength_diff"].mean()),
                "raw": float(y_sum / e_era),
                "situation": float(y_sum / e_ctx),
                "referee": float(y_sum / exp_ref),
                "ref_lo": lo_ref,
                "ref_hi": hi_ref,
                "ref_draw": float(mult.mean()),
                "sep_raw": bool((poisson_ci(y_sum, e_era)[0] > 1) or (poisson_ci(y_sum, e_era)[1] < 1)),
                "sep_situation": bool((lo_ctx > 1) or (hi_ctx < 1)),
                "sep_referee": bool((lo_ref > 1) or (hi_ref < 1)),
                "p_raw": poisson_two_sided(y_sum, exp_ref),
                "p_era": poisson_two_sided(y_sum, e_era),
            })

        cdf = pd.DataFrame(rows)
        cdf["p_bh_league"] = bh_adjust(cdf["p_raw"].to_numpy())
        cdf["p_bh_era"] = bh_adjust(cdf["p_era"].to_numpy())
        all_club_rows.append(cdf)

        total_tm += int(len(tm))
        total_refs += int(known_refs["Referee"].nunique())
        total_refs_40 += int(len(busy))

        ref_results[code] = {
            "country": COMPETITIONS[code].country,
            "team_matches": int(len(tm)),
            "known_ref_share": float(tm["Referee"].notna().mean()),
            "referees_total": int(known_refs["Referee"].nunique()),
            "referees_40plus": int(len(busy)),
            "ref_mult_min": float(busy["ref_mult"].min()),
            "ref_mult_max": float(busy["ref_mult"].max()),
            "ref_mult_median": float(busy["ref_mult"].median()),
            "ref_mult_spread": float(busy["ref_mult"].max() - busy["ref_mult"].min()),
            "clubs_ranked": int(len(cdf)),
            "min_club_matches": min_club_m,
            "ref_draw_min": float(cdf["ref_draw"].min()),
            "ref_draw_max": float(cdf["ref_draw"].max()),
            "sep_raw": int(cdf["sep_raw"].sum()),
            "sep_situation": int(cdf["sep_situation"].sum()),
            "sep_referee": int(cdf["sep_referee"].sum()),
            "bh_surviving_era": int((cdf["p_bh_era"] < 0.10).sum()),
            "bh_surviving_ref": int((cdf["p_bh_league"] < 0.10).sum()),
            "max_abs_ref_shift": float((cdf["referee"] - cdf["situation"]).abs().max()),
            "rms_ref_shift": float(np.sqrt(np.mean((cdf["referee"] - cdf["situation"]) ** 2))),
        }

    all_ref_clubs = pd.concat(all_club_rows, ignore_index=True)
    all_ref_clubs["p_bh_pooled80"] = bh_adjust(all_ref_clubs["p_raw"].to_numpy())

    return {
        "total_team_matches": total_tm,
        "total_referees": total_refs,
        "total_referees_40plus": total_refs_40,
        "total_clubs": int(len(all_ref_clubs)),
        "overall_ref_draw_min": float(all_ref_clubs["ref_draw"].min()),
        "overall_ref_draw_max": float(all_ref_clubs["ref_draw"].max()),
        "overall_rms_ref_shift": float(np.sqrt(np.mean((all_ref_clubs["referee"] - all_ref_clubs["situation"]) ** 2))),
        "overall_max_ref_shift": float((all_ref_clubs["referee"] - all_ref_clubs["situation"]).abs().max()),
        "overall_corr_sit_ref": float(stats.pearsonr(all_ref_clubs["situation"], all_ref_clubs["referee"])[0]),
        "by_league": ref_results,
        "clubs": all_ref_clubs.to_dict(orient="records"),
    }


def run_live_scan(directory: Path) -> dict:
    """Run the 2026-27 cross-league Beta-Binomial shrinkage scan across all 11 leagues."""
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    current = matches[matches["season"] == "2627"]
    ts = team_season(current)
    out = []
    for (div, _season), g in ts.groupby(["Div", "season"], sort=False):
        g = g.reset_index(drop=True)
        prior = beta_binomial_prior(g["yellows"], g["fouls"])
        est = shrink_beta_binomial(g["yellows"], g["fouls"], prior)
        post_a = prior.alpha + g["yellows"].to_numpy(float)
        post_b = prior.beta + (g["fouls"].to_numpy(float) - g["yellows"].to_numpy(float))
        g["p_below_league"] = stats.beta.cdf(prior.mean, post_a, post_b)
        g["p_above_league"] = 1.0 - g["p_below_league"]
        g["league_mean_rate"] = prior.mean
        g["league_fouls_per_yellow"] = 1.0 / prior.mean
        g["shrunk_rate"] = est["shrunk"]
        g["fouls_per_yellow"] = np.where(
            g["yellows"] > 0, g["fouls"] / g["yellows"].replace(0, np.nan), np.inf
        )
        g["fouls_per_yellow_shrunk"] = 1.0 / est["shrunk"]
        g["fpy_lo"] = 1.0 / est["upper"]
        g["fpy_hi"] = 1.0 / est["lower"]
        g["detectable"] = prior.detectable_variance
        g["league"] = div
        out.append(g)
    scanned = pd.concat(out, ignore_index=True)
    top_lenient = scanned.sort_values("fouls_per_yellow", ascending=False).head(12)
    strong_below = scanned[scanned["p_below_league"] > 0.95].sort_values("p_below_league", ascending=False)
    strong_above = scanned[scanned["p_above_league"] > 0.95].sort_values("p_above_league", ascending=False)

    return {
        "season": "2026-27",
        "clubs_scanned": int(len(scanned)),
        "leagues_scanned": int(scanned["league"].nunique()),
        "latest_date": str(current["Date"].max().date()),
        "p_below_95_count": int(len(strong_below)),
        "p_above_95_count": int(len(strong_above)),
        "expected_by_chance_05": float(0.05 * len(scanned)),
        "detectable_leagues": int(scanned.groupby("league")["detectable"].first().sum()),
        "top_lenient_raw": top_lenient[[
            "league", "team", "matches", "fouls", "yellows",
            "fouls_per_yellow", "fouls_per_yellow_shrunk", "fpy_lo", "fpy_hi",
            "league_fouls_per_yellow", "p_below_league"
        ]].replace(np.inf, 999.0).to_dict(orient="records"),
        "strong_below_95": strong_below[[
            "league", "team", "matches", "fouls", "yellows",
            "fouls_per_yellow", "fouls_per_yellow_shrunk", "fpy_lo", "fpy_hi",
            "league_fouls_per_yellow", "p_below_league"
        ]].replace(np.inf, 999.0).to_dict(orient="records"),
    }


def main() -> None:
    directory = ROOT / "data" / "snapshots" / "2026-W36"
    tm = load_completed_team_matches(directory)

    out_parts = []
    league_summary = {}
    persistence = json.loads((ROOT / "reports/04-how-much-of-an-index-is-real/persistence.json").read_text())
    pers_by_lg = {d["lg"]: d for d in persistence["per_league"]}
    agg_json = json.loads((ROOT / "reports/02-fouling-with-impunity/aggregation.json").read_text())

    for lg, g_lg in tm.groupby("league", sort=True):
        g_lg = g_lg.copy()
        era = g_lg.groupby("season").apply(
            lambda s: s.yellows.sum() / s.fouls.sum(), include_groups=False
        ).rename("lg_ypf")
        g_lg = g_lg.merge(era, left_on="season", right_index=True)
        g_lg["exp_raw"] = g_lg["fouls"] * g_lg["lg_ypf"]

        aff_shares = []
        exp_aff = np.zeros(len(g_lg))
        for season, idx in g_lg.groupby("season").groups.items():
            sub = g_lg.loc[idx]
            f_arr = sub["fouls"].to_numpy(float)
            y_arr = sub["yellows"].to_numpy(float)
            A = np.column_stack([np.ones(len(f_arr)), f_arr])
            a_hat, b_hat = np.linalg.lstsq(A, y_arr, rcond=None)[0]
            a_hat = max(float(a_hat), 0.0)
            b_hat = max(float(b_hat), 0.01)
            pred = np.maximum(a_hat + b_hat * f_arr, 0.05)
            pred = pred * (y_arr.sum() / pred.sum())
            exp_aff[g_lg.index.get_indexer(idx)] = pred
            if y_arr.mean() > 0:
                aff_shares.append(float(a_hat / y_arr.mean()))
        g_lg["exp_aff"] = exp_aff

        g_lg["band"] = pd.cut(g_lg["strength_diff"], BANDS, labels=NAMES)
        band_mult = g_lg.groupby("band", observed=True).apply(
            lambda b: b.yellows.sum() / b.exp_raw.sum(), include_groups=False
        ).rename("band_mult")
        g_lg = g_lg.merge(band_mult, left_on="band", right_index=True, how="left")
        g_lg["exp_band_sit"] = g_lg["exp_raw"] * g_lg["band_mult"].astype(float).fillna(1.0)

        s_arr = g_lg["strength_diff"].to_numpy(float)
        y_arr = g_lg["yellows"].to_numpy(float)
        g_lg["exp_quartic_raw"] = fit_quartic_poisson(s_arr, y_arr, g_lg["exp_raw"].to_numpy(float))
        g_lg["exp_quartic_aff"] = fit_quartic_poisson(s_arr, y_arr, g_lg["exp_aff"].to_numpy(float))

        team_str = g_lg.groupby(["season", "team"])["strength_diff"].mean().rename("s_team_season")
        g_lg = g_lg.merge(team_str, on=["season", "team"], how="left")
        g_lg = g_lg.merge(
            team_str.rename("s_opp_season"),
            left_on=["season", "opponent"],
            right_index=True,
            how="left",
        )
        g_lg["exp_fixture"] = fit_fixture_poisson(
            s_arr,
            g_lg["s_team_season"].fillna(0.0).to_numpy(float),
            g_lg["s_opp_season"].fillna(0.0).to_numpy(float),
            y_arr,
            g_lg["exp_aff"].to_numpy(float),
        )

        g_lg["opp_tercile"] = g_lg.groupby("season")["s_opp_season"].transform(
            lambda s: pd.qcut(s, 3, labels=["weak", "mid", "strong"], duplicates="drop")
        )
        terc = g_lg.groupby("opp_tercile", observed=True).apply(
            lambda x: x.yellows.sum() / x.exp_raw.sum(), include_groups=False
        )

        league_summary[lg] = {
            "country": COMPETITIONS[lg].country,
            "name": COMPETITIONS[lg].name,
            "matches": int(len(g_lg) // 2),
            "team_matches": int(len(g_lg)),
            "seasons": int(g_lg["season"].nunique()),
            "fouls_per_team_match": float(g_lg["fouls"].mean()),
            "yellows_per_team_match": float(g_lg["yellows"].mean()),
            "fouls_per_yellow": float(g_lg["fouls"].sum() / g_lg["yellows"].sum()),
            "intercept_share_mean": float(np.mean(aff_shares)),
            "heavy_underdog_mult": float(band_mult.get("heavy underdog", np.nan)),
            "heavy_favourite_mult": float(band_mult.get("heavy favourite", np.nan)),
            "strength_gradient": float(agg_json["gradient_by_league"][lg]["gradient"]),
            "home_gd": float(agg_json["gradient_by_league"][lg]["home_gd"]),
            "opp_tercile_weak": float(terc.get("weak", np.nan)),
            "opp_tercile_mid": float(terc.get("mid", np.nan)),
            "opp_tercile_strong": float(terc.get("strong", np.nan)),
            "persistence_r": float(pers_by_lg[lg]["r"]),
            "persistence_pairs": int(pers_by_lg[lg]["pairs"]),
        }
        out_parts.append(g_lg)

    tm_all = pd.concat(out_parts, ignore_index=True)

    club_agg = tm_all.groupby(["league", "team"], as_index=False).agg(
        n=("fouls", "size"),
        seasons=("season", "nunique"),
        fouls=("fouls", "sum"),
        yellows=("yellows", "sum"),
        strength=("strength_diff", "mean"),
        e_raw=("exp_raw", "sum"),
        e_aff=("exp_aff", "sum"),
        e_band_sit=("exp_band_sit", "sum"),
        e_quartic_raw=("exp_quartic_raw", "sum"),
        e_quartic_aff=("exp_quartic_aff", "sum"),
        e_fixture=("exp_fixture", "sum"),
    )

    opp_agg = tm_all.groupby(["league", "opponent"], as_index=False).agg(
        opp_yellows=("yellows", "sum"),
        opp_e_raw=("exp_raw", "sum"),
        opp_e_quartic_raw=("exp_quartic_raw", "sum"),
        opp_e_quartic_aff=("exp_quartic_aff", "sum"),
    ).rename(columns={"opponent": "team"})
    club_agg = club_agg.merge(opp_agg, on=["league", "team"], how="left")

    for col, ecol in [
        ("idx_raw", "e_raw"),
        ("idx_aff", "e_aff"),
        ("idx_band_sit", "e_band_sit"),
        ("idx_quartic_raw", "e_quartic_raw"),
        ("idx_quartic_aff", "e_quartic_aff"),
        ("idx_fixture", "e_fixture"),
    ]:
        club_agg[col] = club_agg["yellows"] / club_agg[ecol]

    club_agg["opp_idx_raw"] = club_agg["opp_yellows"] / club_agg["opp_e_raw"]
    club_agg["opp_idx_quartic"] = club_agg["opp_yellows"] / club_agg["opp_e_quartic_raw"]

    clubs_150 = club_agg[club_agg["n"] >= 150].copy().reset_index(drop=True)
    for spec in ["idx_raw", "idx_aff", "idx_band_sit", "idx_quartic_raw", "idx_quartic_aff", "idx_fixture"]:
        ecol = "e_" + spec[4:]
        p_vals = np.array([
            poisson_two_sided(int(y), float(e))
            for y, e in zip(clubs_150["yellows"], clubs_150[ecol], strict=True)
        ])
        q_univ = bh_adjust(p_vals)
        q_within = np.zeros(len(clubs_150))
        for lg, idx in clubs_150.groupby("league").groups.items():
            q_within[clubs_150.index.get_indexer(idx)] = bh_adjust(p_vals[clubs_150.index.get_indexer(idx)])
        clubs_150[f"p_{spec[4:]}"] = p_vals
        clubs_150[f"q_univ_{spec[4:]}"] = q_univ
        clubs_150[f"q_lg_{spec[4:]}"] = q_within
        bounds = [poisson_ci(y, e) for y, e in zip(clubs_150["yellows"], clubs_150[ecol], strict=True)]
        clubs_150[f"lo_{spec[4:]}"] = [b[0] for b in bounds]
        clubs_150[f"hi_{spec[4:]}"] = [b[1] for b in bounds]

    for lg, g in clubs_150.groupby("league"):
        league_summary[lg]["clubs_150"] = int(len(g))
        league_summary[lg]["bh_raw_10"] = int((g["q_lg_raw"] < 0.10).sum())
        league_summary[lg]["bh_band_sit_10"] = int((g["q_lg_band_sit"] < 0.10).sum())
        league_summary[lg]["bh_fixture_10"] = int((g["q_lg_fixture"] < 0.10).sum())

    q75 = float(clubs_150["strength"].quantile(0.75))
    q25 = float(clubs_150["strength"].quantile(0.25))
    top_q = clubs_150[clubs_150["strength"] >= q75]
    bot_q = clubs_150[clubs_150["strength"] <= q25]
    elite_26 = clubs_150[clubs_150["strength"] >= 1.0]

    universe_cohorts = {
        "corr_strength_raw": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_raw"])[0]),
        "corr_strength_raw_p": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_raw"])[1]),
        "corr_strength_aff": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_aff"])[0]),
        "corr_strength_band_sit": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_band_sit"])[0]),
        "corr_strength_quartic_raw": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_quartic_raw"])[0]),
        "corr_strength_quartic_aff": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_quartic_aff"])[0]),
        "corr_strength_fixture": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_fixture"])[0]),
        "corr_strength_fixture_p": float(stats.pearsonr(clubs_150["strength"], clubs_150["idx_fixture"])[1]),
        "top_quartile_n": int(len(top_q)),
        "bot_quartile_n": int(len(bot_q)),
        "top_vs_bot_raw": [float(top_q["idx_raw"].mean()), float(bot_q["idx_raw"].mean()), float(stats.ttest_ind(top_q["idx_raw"], bot_q["idx_raw"]).pvalue)],
        "top_vs_bot_quartic": [float(top_q["idx_quartic_raw"].mean()), float(bot_q["idx_quartic_raw"].mean()), float(stats.ttest_ind(top_q["idx_quartic_raw"], bot_q["idx_quartic_raw"]).pvalue)],
        "top_vs_bot_fixture": [float(top_q["idx_fixture"].mean()), float(bot_q["idx_fixture"].mean()), float(stats.ttest_ind(top_q["idx_fixture"], bot_q["idx_fixture"]).pvalue)],
        "elite_contenders_s_ge_1": {
            "n": int(len(elite_26)),
            "mean_raw": float(elite_26["idx_raw"].mean()),
            "median_raw": float(elite_26["idx_raw"].median()),
            "mean_band_sit": float(elite_26["idx_band_sit"].mean()),
            "mean_quartic_raw": float(elite_26["idx_quartic_raw"].mean()),
            "mean_fixture": float(elite_26["idx_fixture"].mean()),
            "median_fixture": float(elite_26["idx_fixture"].median()),
            "mean_opp_quartic": float(elite_26["opp_idx_quartic"].mean()),
        },
        "bh_univ_10_counts": {
            "raw": int((clubs_150["q_univ_raw"] < 0.10).sum()),
            "aff": int((clubs_150["q_univ_aff"] < 0.10).sum()),
            "band_sit": int((clubs_150["q_univ_band_sit"] < 0.10).sum()),
            "quartic_raw": int((clubs_150["q_univ_quartic_raw"] < 0.10).sum()),
            "quartic_aff": int((clubs_150["q_univ_quartic_aff"] < 0.10).sum()),
            "fixture": int((clubs_150["q_univ_fixture"] < 0.10).sum()),
        },
    }

    ref_decomp = run_referee_decomposition(directory)
    live_scan_w36 = run_live_scan(directory)
    live_scan_w42 = run_live_scan(ROOT / "data" / "snapshots" / "2026-W42")

    # Print summary tables for inspection
    print("\n=== LEAGUE SUMMARY TABLE (11 Leagues) ===")
    lg_df = pd.DataFrame.from_dict(league_summary, orient="index")
    print(lg_df[[
        "country", "matches", "clubs_150", "intercept_share_mean",
        "heavy_underdog_mult", "heavy_favourite_mult",
        "opp_tercile_weak", "opp_tercile_strong", "persistence_r",
        "bh_raw_10", "bh_band_sit_10", "bh_fixture_10"
    ]].round(3).to_string())

    print("\n=== REFEREE DECOMPOSITION ACROSS E0, SC0, P1 ===")
    ref_df = pd.DataFrame.from_dict(ref_decomp["by_league"], orient="index")
    print(ref_df[[
        "country", "team_matches", "referees_total", "referees_40plus",
        "ref_mult_min", "ref_mult_max", "clubs_ranked",
        "ref_draw_min", "ref_draw_max", "rms_ref_shift",
        "sep_raw", "sep_situation", "sep_referee", "bh_surviving_ref"
    ]].round(3).to_string())

    print(f"\nOverall 3-league referee summary: {ref_decomp['total_team_matches']:,} team-matches, "
          f"{ref_decomp['total_referees']} refs ({ref_decomp['total_referees_40plus']} with >=40m), "
          f"{ref_decomp['total_clubs']} clubs, ref_draw in [{ref_decomp['overall_ref_draw_min']:.3f}, {ref_decomp['overall_ref_draw_max']:.3f}], "
          f"RMS shift {ref_decomp['overall_rms_ref_shift']:.4f}, corr(sit, ref) = {ref_decomp['overall_corr_sit_ref']:.4f}")

    # Top and bottom clubs in referee decomposition (80 clubs across E0, SC0, P1)
    ref_clubs_df = pd.DataFrame(ref_decomp["clubs"]).sort_values("referee", ascending=False)
    print("\n=== TOP 10 & BOTTOM 10 REFEREE-ADJUSTED CLUBS (E0, SC0, P1) ===")
    print(ref_clubs_df.head(10)[["league", "club", "n", "strength", "raw", "situation", "referee", "ref_lo", "ref_hi", "ref_draw", "p_bh_league"]].round(3).to_string(index=False))
    print("---")
    print(ref_clubs_df.tail(10)[["league", "club", "n", "strength", "raw", "situation", "referee", "ref_lo", "ref_hi", "ref_draw", "p_bh_league"]].round(3).to_string(index=False))

    # Top and bottom clubs in 246-club universe under fixture-adjusted and band-situation-adjusted
    print("\n=== clubs_150 SURVIVING BH (q_univ_fixture < 0.10) ===")
    surv_fix = clubs_150[clubs_150["q_univ_fixture"] < 0.10].sort_values("idx_fixture", ascending=False)
    print(surv_fix[["league", "team", "n", "strength", "idx_raw", "idx_band_sit", "idx_fixture", "lo_fixture", "hi_fixture", "q_univ_fixture", "q_lg_fixture"]].round(3).to_string(index=False))

    results = {
        "snapshot": directory.name,
        "team_matches_total": int(len(tm)),
        "team_matches_positive_fouls": int((tm["fouls"] > 0).sum()),
        "clubs_150_count": int(len(clubs_150)),
        "clubs_80_count": int((club_agg["n"] >= 80).sum()),
        "clubs_all_count": int(len(club_agg)),
        "universe_cohorts": universe_cohorts,
        "league_summary": league_summary,
        "referee_decomposition": ref_decomp,
        "live_scan_2627": live_scan_w36,
        "live_scan_2627_w42": live_scan_w42,
        "clubs_150": clubs_150.to_dict(orient="records"),
    }
    out_path = ROOT / "paper" / "universe_results.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
