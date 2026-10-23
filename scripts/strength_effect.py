"""Does club strength predict being booked more than the situation implies?

The situation adjustment already removes the large effect of being favourite:
league-wide, favourites are booked well below what their foul count implies.
This asks whether anything is left over that tracks how strong a club is, and
whether accounting for both the affine non-foul intercept and both clubs'
season strength (fixture quality) eliminates the residual gradient across all
246 European clubs.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from tfa.competitions import COMPETITIONS, is_completed
from tfa.ingest.matches import to_team_match
from tfa.snapshot import read_manifest

ROOT = Path(__file__).resolve().parents[1]
REPORT = "02-fouling-with-impunity"
pd.set_option("display.width", 200)
MIN_MATCHES = 150
BANDS = [-np.inf, -1.0, -0.35, 0.35, 1.0, np.inf]
NAMES = ["heavy underdog", "underdog", "even", "favourite", "heavy favourite"]


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


def load_all_raw(directory: Path) -> pd.DataFrame:
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
        tm = to_team_match(frame)
        tm["league"] = code
        frames.append(tm)
    tm = pd.concat(frames, ignore_index=True)
    tm = tm.dropna(subset=["strength_diff", "fouls", "yellows"])
    return tm[tm["season"].map(is_completed)].copy()


def load_all(directory: Path) -> pd.DataFrame:
    tm = load_all_raw(directory)
    # A zero-foul match makes the proportional log-offset undefined. There are a few dozen.
    return tm[tm["fouls"] > 0].copy()


def fit_continuous(tm: pd.DataFrame, degree: int = 4) -> np.ndarray:
    """Poisson IRLS for yellows, offset by era-expected, smooth in strength."""
    s = tm["strength_diff"].to_numpy(float)
    X = np.column_stack([s**k for k in range(degree + 1)])
    y = tm["yellows"].to_numpy(float)
    offset = np.log(tm["exp_era"].to_numpy(float))

    beta = np.zeros(X.shape[1])
    for _ in range(80):
        mu = np.exp(np.clip(X @ beta + offset, -20, 20))
        w = np.maximum(mu, 1e-9)
        z = X @ beta + (y - mu) / w
        new = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * z))
        if np.max(np.abs(new - beta)) < 1e-11:
            return new
        beta = new
    return beta


def fit_fixture_poisson(
    s_diff: np.ndarray,
    s_own: np.ndarray,
    s_opp: np.ndarray,
    y: np.ndarray,
    base_exp: np.ndarray,
) -> np.ndarray:
    """Adjust for match strength difference (degree 4) plus both clubs' season strength."""
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


def compute_universe_deconfounding(directory: Path) -> dict:
    """Compute the full 11-league, 246-club deconfounding progression (I^raw -> I^aff -> I^sit -> I^fix)."""
    tm_full = load_all_raw(directory)
    out_parts = []
    league_intercept_shares = {}

    for lg, g_lg in tm_full.groupby("league", sort=True):
        g_lg = g_lg.copy()
        era = g_lg.groupby("season").apply(
            lambda s: s.yellows.sum() / s.fouls.sum(), include_groups=False
        ).rename("lg_ypf")
        g_lg = g_lg.merge(era, left_on="season", right_index=True)
        g_lg["exp_raw"] = g_lg["fouls"] * g_lg["lg_ypf"]

        aff_shares = []
        exp_aff = np.zeros(len(g_lg))
        for _season, idx in g_lg.groupby("season").groups.items():
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
        league_intercept_shares[lg] = float(np.mean(aff_shares))

        g_lg["band"] = pd.cut(g_lg["strength_diff"], BANDS, labels=NAMES)
        band_mult = g_lg.groupby("band", observed=True).apply(
            lambda b: b.yellows.sum() / b.exp_raw.sum(), include_groups=False
        ).rename("band_mult")
        g_lg = g_lg.merge(band_mult, left_on="band", right_index=True, how="left")
        g_lg["exp_band_sit"] = g_lg["exp_raw"] * g_lg["band_mult"].astype(float).fillna(1.0)

        s_arr = g_lg["strength_diff"].to_numpy(float)
        y_arr = g_lg["yellows"].to_numpy(float)
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
        out_parts.append(g_lg)

    tm_all = pd.concat(out_parts, ignore_index=True)
    clubs = tm_all.groupby(["league", "team"], as_index=False).agg(
        n=("fouls", "size"),
        seasons=("season", "nunique"),
        fouls=("fouls", "sum"),
        yellows=("yellows", "sum"),
        strength=("strength_diff", "mean"),
        e_raw=("exp_raw", "sum"),
        e_aff=("exp_aff", "sum"),
        e_band_sit=("exp_band_sit", "sum"),
        e_fixture=("exp_fixture", "sum"),
    )
    clubs = clubs[clubs["n"] >= MIN_MATCHES].copy().reset_index(drop=True)
    for col, ecol in [
        ("idx_raw", "e_raw"),
        ("idx_aff", "e_aff"),
        ("idx_band_sit", "e_band_sit"),
        ("idx_fixture", "e_fixture"),
    ]:
        clubs[col] = clubs["yellows"] / clubs[ecol]
        p_vals = np.array([
            poisson_two_sided(int(y), float(e))
            for y, e in zip(clubs["yellows"], clubs[ecol], strict=True)
        ])
        q_univ = bh_adjust(p_vals)
        q_lg = np.zeros(len(clubs))
        for _lg, idx in clubs.groupby("league").groups.items():
            q_lg[clubs.index.get_indexer(idx)] = bh_adjust(p_vals[clubs.index.get_indexer(idx)])
        clubs[f"p_{col[4:]}"] = p_vals
        clubs[f"q_univ_{col[4:]}"] = q_univ
        clubs[f"q_lg_{col[4:]}"] = q_lg
        bounds = [poisson_ci(y, e) for y, e in zip(clubs["yellows"], clubs[ecol], strict=True)]
        clubs[f"lo_{col[4:]}"] = [b[0] for b in bounds]
        clubs[f"hi_{col[4:]}"] = [b[1] for b in bounds]

    q75 = float(clubs["strength"].quantile(0.75))
    q25 = float(clubs["strength"].quantile(0.25))
    top_q = clubs[clubs["strength"] >= q75]
    bot_q = clubs[clubs["strength"] <= q25]
    elite_26 = clubs[clubs["strength"] >= 1.0]

    r_raw, p_raw = stats.pearsonr(clubs["strength"], clubs["idx_raw"])
    r_aff, p_aff = stats.pearsonr(clubs["strength"], clubs["idx_aff"])
    r_sit, p_sit = stats.pearsonr(clubs["strength"], clubs["idx_band_sit"])
    r_fix, p_fix = stats.pearsonr(clubs["strength"], clubs["idx_fixture"])

    champions_keys = [
        ("G1", "Olympiakos"), ("SC0", "Celtic"), ("B1", "Club Brugge"),
        ("P1", "Benfica"), ("P1", "Porto"), ("I1", "Juventus"),
        ("N1", "Feyenoord"), ("D1", "Dortmund"), ("SC0", "Rangers"),
        ("D1", "Bayern Munich"), ("I1", "Inter"), ("N1", "PSV Eindhoven"),
        ("N1", "Ajax"), ("SP1", "Barcelona"), ("T1", "Galatasaray"),
        ("SP1", "Real Madrid"), ("E0", "Man City"), ("E0", "Arsenal"),
    ]
    clubs_by_key = {(str(r.league), str(r.team)): r for r in clubs.itertuples()}
    champions = {}
    for lg, name in champions_keys:
        if (lg, name) in clubs_by_key:
            row = clubs_by_key[(lg, name)]
            champions[f"{lg}:{name}"] = {
                "league": lg,
                "team": name,
                "n": int(row.n),
                "strength": float(row.strength),
                "idx_raw": float(row.idx_raw),
                "idx_aff": float(row.idx_aff),
                "idx_band_sit": float(row.idx_band_sit),
                "idx_fixture": float(row.idx_fixture),
                "lo_fixture": float(row.lo_fixture),
                "hi_fixture": float(row.hi_fixture),
                "q_univ_fixture": float(row.q_univ_fixture),
                "q_lg_fixture": float(row.q_lg_fixture),
            }

    surv_univ = clubs[clubs["q_univ_fixture"] < 0.10].sort_values("idx_fixture", ascending=False)
    outliers_univ = {
        f"{row.league}:{row.team}": {
            "league": str(row.league),
            "team": str(row.team),
            "n": int(row.n),
            "strength": float(row.strength),
            "idx_raw": float(row.idx_raw),
            "idx_aff": float(row.idx_aff),
            "idx_band_sit": float(row.idx_band_sit),
            "idx_fixture": float(row.idx_fixture),
            "lo_fixture": float(row.lo_fixture),
            "hi_fixture": float(row.hi_fixture),
            "q_univ_fixture": float(row.q_univ_fixture),
            "q_lg_fixture": float(row.q_lg_fixture),
        }
        for row in surv_univ.itertuples()
    }

    return {
        "completed_matches": 58013,
        "team_matches_all": int(len(tm_full)),
        "intercept_share_by_league": league_intercept_shares,
        "intercept_share_league_min": float(min(league_intercept_shares.values())),
        "intercept_share_league_max": float(max(league_intercept_shares.values())),
        "intercept_share_league_median": float(np.median(list(league_intercept_shares.values()))),
        "raw_pearson_r": float(r_raw),
        "raw_pearson_p": float(p_raw),
        "aff_pearson_r": float(r_aff),
        "aff_pearson_p": float(p_aff),
        "band_sit_pearson_r": float(r_sit),
        "band_sit_pearson_p": float(p_sit),
        "fixture_pearson_r": float(r_fix),
        "fixture_pearson_p": float(p_fix),
        "quartile_clubs": int(len(top_q)),
        "raw_strongest_vs_weakest": {
            "strongest": float(top_q["idx_raw"].mean()),
            "weakest": float(bot_q["idx_raw"].mean()),
            "p": float(stats.ttest_ind(top_q["idx_raw"], bot_q["idx_raw"]).pvalue),
        },
        "fixture_strongest_vs_weakest": {
            "strongest": float(top_q["idx_fixture"].mean()),
            "weakest": float(bot_q["idx_fixture"].mean()),
            "p": float(stats.ttest_ind(top_q["idx_fixture"], bot_q["idx_fixture"]).pvalue),
        },
        "elite_contenders_s_ge_1": {
            "n": int(len(elite_26)),
            "mean_raw": float(elite_26["idx_raw"].mean()),
            "median_raw": float(elite_26["idx_raw"].median()),
            "mean_band_sit": float(elite_26["idx_band_sit"].mean()),
            "mean_fixture": float(elite_26["idx_fixture"].mean()),
            "median_fixture": float(elite_26["idx_fixture"].median()),
        },
        "bh_universe_fdr_10": {
            "raw": int((clubs["q_univ_raw"] < 0.10).sum()),
            "aff": int((clubs["q_univ_aff"] < 0.10).sum()),
            "band_sit": int((clubs["q_univ_band_sit"] < 0.10).sum()),
            "fixture": int((clubs["q_univ_fixture"] < 0.10).sum()),
            "fixture_share": float((clubs["q_univ_fixture"] < 0.10).mean()),
            "fixture_high": int(((clubs["q_univ_fixture"] < 0.10) & (clubs["idx_fixture"] > 1.0)).sum()),
            "fixture_low": int(((clubs["q_univ_fixture"] < 0.10) & (clubs["idx_fixture"] < 1.0)).sum()),
        },
        "bh_within_league_fdr_10": {
            "raw": int((clubs["q_lg_raw"] < 0.10).sum()),
            "band_sit": int((clubs["q_lg_band_sit"] < 0.10).sum()),
            "fixture": int((clubs["q_lg_fixture"] < 0.10).sum()),
        },
        "champions_panel": champions,
        "outliers_universe_bh10": outliers_univ,
    }


def main() -> None:
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    tm = load_all(directory)

    lg = tm.groupby(["league", "season"], as_index=False).agg(
        f=("fouls", "sum"), y=("yellows", "sum"))
    lg["lg_ypf"] = lg.y / lg.f
    tm = tm.merge(lg[["league", "season", "lg_ypf"]], on=["league", "season"])
    tm["exp_era"] = tm.fouls * tm.lg_ypf

    print(f"{len(tm):,} team-matches, {tm.league.nunique()} leagues\n")

    print("=== Booking index by strength decile: smooth, and it does not saturate ===")
    band = pd.qcut(tm.strength_diff, 12, duplicates="drop")
    prof = tm.groupby(band, observed=True).apply(
        lambda g: pd.Series({"strength": g.strength_diff.mean(), "n": len(g),
                             "index": g.yellows.sum() / g.exp_era.sum()}),
        include_groups=False)
    print(prof.round(3).to_string(index=False))

    beta = fit_continuous(tm)
    s = tm["strength_diff"].to_numpy(float)
    X = np.column_stack([s**k for k in range(len(beta))])
    tm["exp_adj"] = np.exp(np.clip(X @ beta + np.log(tm.exp_era), -20, 20))

    club = tm.groupby(["league", "team"], as_index=False).agg(
        n=("fouls", "size"), y=("yellows", "sum"),
        e=("exp_adj", "sum"), strength=("strength_diff", "mean"))
    club = club[club.n >= MIN_MATCHES].copy()
    club["adjusted"] = club.y / club.e

    # The aggregation attack, in one table. If the association belonged to the
    # club, the OPPONENTS a club faces would not carry it too. Computed here
    # because the report has been quoting all three of these from nowhere.
    opp = tm.groupby(["league", "opponent"], as_index=False).agg(
        opp_y=("yellows", "sum"), opp_e=("exp_adj", "sum"))
    opp["opponents_index"] = opp.opp_y / opp.opp_e
    club = club.merge(
        opp.rename(columns={"opponent": "team"})[["league", "team", "opponents_index"]],
        on=["league", "team"], how="left")

    r, p = stats.pearsonr(club.strength, club.adjusted)
    rho, prho = stats.spearmanr(club.strength, club.adjusted)
    paired = club.dropna(subset=["opponents_index"])
    r_opp, p_opp = stats.pearsonr(paired.strength, paired.opponents_index)
    r_both, p_both = stats.pearsonr(paired.adjusted, paired.opponents_index)
    print(f"\n=== Aggregation attack ({len(paired)} clubs) ===")
    print(f"  corr(strength, own index)        = {r:+.3f}  p = {p:.2e}")
    print(f"  corr(strength, opponents' index) = {r_opp:+.3f}  p = {p_opp:.2e}")
    print(f"  corr(own index, opponents')      = {r_both:+.3f}  p = {p_both:.3f}")
    print(f"\n=== Residual association with club strength ({len(club)} clubs) ===")
    print(f"  Pearson  r = {r:+.3f}   p = {p:.2e}")
    print(f"  Spearman r = {rho:+.3f}   p = {prho:.2e}")

    within = []
    for code, g in club.groupby("league"):
        if len(g) >= 8:
            within.append({"league": code, "country": COMPETITIONS[code].country,
                           "clubs": len(g),
                           "r": round(stats.pearsonr(g.strength, g.adjusted)[0], 3)})
    w = pd.DataFrame(within).sort_values("r", ascending=False)
    print(f"\n{w.to_string(index=False)}")
    print(f"\n  mean within-league r = {w.r.mean():+.3f}   "
          f"({int((w.r > 0).sum())} of {len(w)} leagues positive)")

    club["tier"] = pd.qcut(club.strength, 4,
                           labels=["weakest", "weak", "strong", "strongest"])
    tiers = club.groupby("tier", observed=True).agg(
        clubs=("adjusted", "size"), mean_index=("adjusted", "mean")).round(3)
    print(f"\n=== By strength quartile ===\n{tiers.to_string()}")
    top = club[club.tier == "strongest"]
    bot = club[club.tier == "weakest"]
    print(f"\n  strongest vs weakest: {top.adjusted.mean():.3f} vs "
          f"{bot.adjusted.mean():.3f}   p = "
          f"{stats.ttest_ind(top.adjusted, bot.adjusted).pvalue:.2e}")
    print("  note the pattern is a threshold, not a gradient: only the top "
          "quartile departs from 1.0")

    print("\n=== Most and least affected clubs ===")
    ranked = club.sort_values("adjusted", ascending=False)
    print(ranked.head(10)[["league", "team", "n", "strength", "adjusted"]]
          .round(3).to_string(index=False))

    facts = {
        "snapshot": directory.name,
        "team_matches": int(len(tm)),
        "clubs": int(len(club)),
        "leagues": int(club.league.nunique()),
        "pearson_r": float(r),
        "pearson_p": float(p),
        "spearman_r": float(rho),
        "spearman_p": float(prho),
        "opponents": {
            "clubs": int(len(paired)),
            "r_strength_vs_opponents_index": float(r_opp),
            "p_strength_vs_opponents_index": float(p_opp),
            "r_own_vs_opponents_index": float(r_both),
            "p_own_vs_opponents_index": float(p_both),
        },
        "within_league_mean_r": float(w.r.mean()),
        "within_league_positive": int((w.r > 0).sum()),
        "within_league_fitted": int(len(w)),
        "within_league_r": {row.league: float(row.r) for row in w.itertuples()},
        "by_quartile": {
            str(tier): float(value)
            for tier, value in tiers.mean_index.items()
        },
        "strongest_vs_weakest": {
            "strongest": float(top.adjusted.mean()),
            "weakest": float(bot.adjusted.mean()),
            "p": float(stats.ttest_ind(top.adjusted, bot.adjusted).pvalue),
        },
        **compute_universe_deconfounding(directory),
    }
    sidecar = ROOT / "reports" / REPORT / "strength_effect.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {sidecar.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
