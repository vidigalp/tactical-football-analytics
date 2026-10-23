"""Generate the four publication-grade vector figures for the consolidated paper.

Reads exclusively from committed JSON sidecars (`paper/universe_results.json` and `reports/*/*.json`).
Outputs:
  paper/figures/fig1.pdf
  paper/figures/fig2.pdf
  paper/figures/fig3.pdf
  paper/figures/fig4.pdf
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 8.2,
    "axes.titlesize": 8.2,
    "axes.titleweight": "bold",
    "axes.labelsize": 8.1,
    "xtick.labelsize": 7.2,
    "ytick.labelsize": 7.1,
    "legend.fontsize": 6.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

NAVY = "#1B365D"
TEAL = "#008080"
CORAL = "#D9534F"
AMBER = "#E69F00"
SLATE = "#6C757D"
LIGHT_GREY = "#E9ECEF"


def make_fig1() -> None:
    story = json.loads((ROOT / "reports/02-fouling-with-impunity/story.json").read_text())
    univ = json.loads((ROOT / "paper/universe_results.json").read_text())

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(7.25, 2.95), gridspec_kw={"width_ratios": [1.0, 1.28]}, constrained_layout=True
    )

    # Panel A: Pre-match expectation band across all 11 European leagues
    bands = ["heavy favourite", "favourite", "even", "underdog", "heavy underdog"]
    labels = ["Heavy\nFav.", "Fav.", "Even", "Under-\ndog", "Heavy\nUnd."]
    x = np.arange(len(bands))
    by_lg = story["all_leagues"]["by_league"]
    all_mat = np.array([[by_lg[lg][b] for b in bands] for lg in sorted(by_lg)])
    ax1.fill_between(
        x, all_mat.min(axis=0), all_mat.max(axis=0),
        color=LIGHT_GREY, alpha=0.7, label="11-league range (min–max)"
    )
    for lg in sorted(by_lg):
        y = [by_lg[lg][b] for b in bands]
        ax1.plot(x, y, color=SLATE, alpha=0.32, linewidth=0.9)

    med_y = np.median(all_mat, axis=0)
    g1_y = [by_lg["G1"][b] for b in bands]
    sp1_y = [by_lg["SP1"][b] for b in bands]
    ax1.plot(
        x, med_y, color=NAVY, marker="o", linewidth=2.1, markersize=4.5,
        label="11-league median (0.856 $\\rightarrow$ 1.098)"
    )
    ax1.plot(
        x, g1_y, color=CORAL, marker="s", linewidth=1.4, markersize=3.6,
        linestyle="--", label="Steepest: G1 (0.778 $\\rightarrow$ 1.158)"
    )
    ax1.plot(
        x, sp1_y, color=TEAL, marker="^", linewidth=1.4, markersize=3.6,
        linestyle="-.", label="Flattest: SP1 (0.907 $\\rightarrow$ 1.038)"
    )
    ax1.axhline(1.0, color="#333333", linestyle=":", linewidth=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Yellow cards / expected from fouls")
    ax1.set_title("(a) Win-Expectation Gradient (11 Leagues, $N=58,013$)")
    ax1.set_ylim(0.73, 1.24)
    ax1.legend(frameon=True, facecolor="white", framealpha=0.92, edgecolor="#CBD5E1", loc="upper left", fontsize=6.1)

    # Panel B: Pan-European club deconfounding across champions & BH-surviving outliers
    clubs_by_key = {(c["league"], c["team"]): c for c in univ["clubs_150"]}
    ref_by_key = {(c["league"], c["club"]): c for c in univ["referee_decomposition"]["clubs"]}

    selected = [
        ("B1", "St. Gilloise", "Union SG (B1)*"),
        ("P1", "Sp Lisbon", "Sporting CP (P1)*"),
        ("E0", "Chelsea", "Chelsea (E0)*"),
        ("SP1", "Getafe", "Getafe (SP1)*"),
        ("P1", "Porto", "FC Porto (P1)"),
        ("E0", "Man City", "Man City (E0)"),
        ("E0", "Arsenal", "Arsenal (E0)"),
        ("SP1", "Real Madrid", "Real Madrid (SP1)"),
        ("D1", "Bayern Munich", "Bayern Munich (D1)"),
        ("SP1", "Barcelona", "Barcelona (SP1)"),
        ("I1", "Juventus", "Juventus (I1)"),
        ("B1", "Club Brugge", "Club Brugge (B1)"),
        ("SC0", "Celtic", "Celtic (SC0)"),
        ("P1", "Benfica", "SL Benfica (P1)"),
        ("G1", "Olympiakos", "Olympiacos (G1)"),
        ("E0", "Liverpool", "Liverpool (E0)*"),
        ("SP1", "Sociedad", "Real Sociedad (SP1)*"),
    ]

    y_pos = np.arange(len(selected))[::-1]
    raw_vals, sit_vals, fix_vals, lo_vals, hi_vals, y_labels = [], [], [], [], [], []
    for lg, team, label in selected:
        c = clubs_by_key[(lg, team)]
        raw_vals.append(c["idx_raw"])
        if (lg, team) in ref_by_key:
            sit_vals.append(ref_by_key[(lg, team)]["referee"])
        else:
            sit_vals.append(c["idx_band_sit"])
        fix_vals.append(c["idx_fixture"])
        lo_vals.append(c["lo_fixture"])
        hi_vals.append(c["hi_fixture"])
        y_labels.append(label)

    ax2.axvline(1.0, color="#333333", linestyle=":", linewidth=0.9)
    for i, (r_v, s_v, f_v, lo, hi) in enumerate(zip(raw_vals, sit_vals, fix_vals, lo_vals, hi_vals)):
        yp = y_pos[i]
        ax2.plot([min(r_v, s_v, f_v), max(r_v, s_v, f_v)], [yp, yp], color="#CBD5E1", linewidth=1.0, zorder=1)
        ax2.errorbar(
            f_v, yp, xerr=[[f_v - lo], [hi - f_v]], fmt="none",
            ecolor=NAVY, elinewidth=1.2, capsize=2.0, zorder=2
        )

    ax2.scatter(
        raw_vals, y_pos, color="white", edgecolor=CORAL, s=28, linewidth=1.4,
        zorder=3, label="Raw proportional ($I^{\\mathrm{raw}}$)"
    )
    ax2.scatter(
        sit_vals, y_pos, color="white", edgecolor=TEAL, marker="^", s=26, linewidth=1.2,
        zorder=4, label="Strength (+ ref.) adj. ($I^{\\mathrm{sit}}/I^{\\mathrm{ref}}$)"
    )
    ax2.scatter(
        fix_vals, y_pos, color=NAVY, s=28, zorder=5,
        label="Full affine + fixture adj. ($I^{\\mathrm{fix}}$, 95% CI)"
    )

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(y_labels, fontsize=6.6)
    ax2.set_xlabel("Booking index (observed / expected yellows)")
    ax2.set_title("(b) Deconfounding Across European Champions & Outliers ($N=246$)")
    ax2.set_xlim(0.72, 1.42)
    ax2.set_ylim(-1.95, len(selected) - 0.25)
    ax2.legend(
        frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1",
        loc="lower right", fontsize=5.8
    )

    fig.savefig(OUT / "fig1.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig2() -> None:
    story = json.loads((ROOT / "reports/02-fouling-with-impunity/story.json").read_text())
    agg = json.loads((ROOT / "reports/02-fouling-with-impunity/aggregation.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.25, 2.45), constrained_layout=True)

    # Panel A: Yellows per foul vs foul count
    ypf = story["yellows_per_foul"]
    f_bins = sorted((float(k), float(v)) for k, v in ypf.items())
    fx = [k for k, _ in f_bins]
    fy = [v for _, v in f_bins]
    ax1.plot(fx, fy, color=NAVY, marker="o", linewidth=2.0, markersize=4.5,
             label="Observed yellows / foul")
    f_grid = np.linspace(4.8, 24.0, 100)
    y_tot = np.array([k * v for k, v in f_bins])
    A = np.column_stack([np.ones(len(fx)), fx])
    a_hat, b_hat = np.linalg.lstsq(A, y_tot, rcond=None)[0]
    ax1.plot(f_grid, (a_hat + b_hat * f_grid) / f_grid, color=CORAL, linestyle="--",
             linewidth=1.5, label=f"Affine fit ($a={a_hat:.2f}, b={b_hat:.3f}$)")
    ax1.axhline(np.mean(fy), color=SLATE, linestyle=":", linewidth=1.1,
                label="Proportional assumption ($a=0$)")
    ax1.set_xlabel("Team fouls committed in match")
    ax1.set_ylabel("Observed yellow cards per foul")
    ax1.set_title("(a) Non-Foul Intercept Dilution (0.197 $\\rightarrow$ 0.122)")
    ax1.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="upper right", fontsize=6.5)

    # Panel B: Multi-level aggregation reversal
    g_by_lg = agg["gradient_by_league"]
    lgs = sorted(g_by_lg.keys())
    h_gd = [g_by_lg[k]["home_gd"] for k in lgs]
    grad = [abs(g_by_lg[k]["gradient"]) for k in lgs]
    ax2.scatter(h_gd, grad, color=NAVY, s=34, zorder=3)
    custom_offsets = {
        "B1": (4, 1),
        "G1": (4, -2),
        "SC0": (4, -3),
        "P1": (4, -2),
        "I1": (4, 1),
        "T1": (4, 1),
        "E0": (4, -1),
        "F1": (4, 1),
        "N1": (4, 1),
        "D1": (4, 1),
        "SP1": (4, 1),
    }
    for k, x_v, y_v in zip(lgs, h_gd, grad):
        dx, dy = custom_offsets.get(k, (3, 2))
        ax2.annotate(k, (x_v, y_v), xytext=(dx, dy), textcoords="offset points", fontsize=6.6, fontweight="bold", color=NAVY)
    m, b = np.polyfit(h_gd, grad, 1)
    xg = np.linspace(min(h_gd) - 0.01, max(h_gd) + 0.01, 50)
    ax2.plot(xg, m * xg + b, color=CORAL, linestyle="--", linewidth=1.4,
             label="Cross-league ($r = +0.782, N = 11$)")
    ax2.plot([], [], color=TEAL, linestyle="-", linewidth=1.4,
             label="3-yr blocks pooled ($r = +0.238, N = 62$)")
    ax2.plot([], [], color=SLATE, linestyle=":", linewidth=1.4,
             label="Within-league blocks ($r = -0.086, p = 0.50$)")
    ax2.set_xlabel("Mean home goal difference (goals / match)")
    ax2.set_ylabel("Strength-gradient magnitude ($|\\beta|$)")
    ax2.set_title("(b) Ecological Fallacy Across Aggregation Levels")
    ax2.set_xlim(0.245, 0.422)
    ax2.set_ylim(0.034, 0.145)
    ax2.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="upper right", fontsize=6.3)

    fig.savefig(OUT / "fig2.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig3() -> None:
    chart = json.loads((ROOT / "reports/03-the-lever-nobody-pulls/chart.json").read_text())
    facts = json.loads((ROOT / "reports/03-the-lever-nobody-pulls/facts.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.25, 2.45), constrained_layout=True)

    # Panel A: Pitch position gradient vs club mean range [48.2, 58.0]
    pos_rows = chart["position"]
    centers = [10, 27.5, 42.5, 57.5, 72.5, 90]
    rates = [r["rate"] for r in pos_rows]
    los = [r["lo"] for r in pos_rows]
    his = [r["hi"] for r in pos_rows]

    ax1.axvspan(facts["club_x_min"], facts["club_x_max"], color=AMBER, alpha=0.25,
                label=f"98-club mean x range [{facts['club_x_min']:.1f}, {facts['club_x_max']:.1f}]")
    ax1.errorbar(centers, rates,
                 yerr=[[r - lo for r, lo in zip(rates, los)],
                       [hi - r for r, hi in zip(rates, his)]],
                 fmt="-o", color=NAVY, linewidth=2.0, markersize=4.5, capsize=2.5,
                 label="Event card rate (95% Wilson CI)")
    ax1.axhline(facts["base_rate"] * 100, color=SLATE, linestyle=":", linewidth=1.0,
                label=f"Base rate ({facts['base_rate']*100:.1f}%)")
    ax1.set_xlabel("Pitch x-coordinate (0 = own goal line, 100 = opp. goal)")
    ax1.set_ylabel("Card probability per foul (%)")
    ax1.set_title("(a) Steep Event Gradient vs. Narrow Club Range")
    ax1.set_xlim(0, 100)
    ax1.set_ylim(5, 36)
    ax1.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="upper right", fontsize=6.5)

    # Panel B: Match minute gradient + halftime reset + late close-score window
    min_rows = chart["minute"]
    m_labels = [r["band"] for r in min_rows]
    m_rates = [r["rate"] for r in min_rows]
    m_los = [r["lo"] for r in min_rows]
    m_his = [r["hi"] for r in min_rows]
    mx = np.arange(len(m_labels))

    ax2.errorbar(mx, m_rates,
                 yerr=[[r - lo for r, lo in zip(m_rates, m_los)],
                       [hi - r for r, hi in zip(m_rates, m_his)]],
                 fmt="-s", color=TEAL, linewidth=1.8, markersize=4.2, capsize=2.5,
                 label="By 15-min band (6.5% to 25.6%)")
    ax2.axhline(facts["tactical_window_rate"] * 100, color=CORAL, linestyle="--", linewidth=1.3,
                label=f"Late close-score window ({facts['tactical_window_rate']*100:.1f}%, $R^2=0.3\\%$)")
    ax2.annotate("Half-time reset:\n16.1% (40–45') $\\rightarrow$ 12.8% (45–50')\n($p = 4.1\\times 10^{-4}$)",
                 xy=(2.55, 15.3), xytext=(0.45, 18.2),
                 arrowprops={"arrowstyle": "->", "color": NAVY, "lw": 0.9},
                 fontsize=6.4, color=NAVY,
                 bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#CBD5E1", "alpha": 0.92})
    ax2.set_xticks(mx)
    ax2.set_xticklabels(m_labels)
    ax2.set_xlabel("Match minute band")
    ax2.set_ylabel("Card probability per foul (%)")
    ax2.set_title("(b) Temporal Escalation & Situational Window")
    ax2.set_ylim(4, 35.5)
    ax2.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="upper left", fontsize=6.5)

    fig.savefig(OUT / "fig3.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig4() -> None:
    pers = json.loads((ROOT / "reports/04-how-much-of-an-index-is-real/persistence.json").read_text())
    shrink = json.loads((ROOT / "reports/04-how-much-of-an-index-is-real/shrinkage.json").read_text())
    openings = json.loads((ROOT / "reports/live-season-portugal/openings.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.25, 2.55), constrained_layout=True)

    # Panel A: Per-league persistence r across 11 leagues vs matched Poisson null
    per_lg = sorted(pers["per_league"], key=lambda d: d["r"])
    lgs = [d["lg"] for d in per_lg]
    rs = [d["r"] for d in per_lg]
    y_pos = np.arange(len(lgs))

    ax1.axvspan(-pers["null_r_max"], pers["null_r_max"], color=LIGHT_GREY, zorder=1,
                label=f"Matched Poisson null max (+{pers['null_r_max']:.3f})")
    ax1.barh(y_pos, rs, color=NAVY, height=0.62, alpha=0.85, zorder=2)
    ax1.axvline(pers["r"], color=CORAL, linestyle="--", linewidth=1.5, zorder=3,
                label=f"Pooled within-league $r = +{pers['r']:.3f}$")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(lgs)
    ax1.set_xlabel("Year-to-year club booking index correlation ($r$)")
    ax1.set_title("(a) Persistence Across 11 Leagues ($N = 2,528$)")
    ax1.set_xlim(-0.06, 0.56)
    ax1.set_ylim(-0.9, 10.7)
    ax1.text(0.285, 3.0,
             f"True variance share: {pers['true_share']*100:.1f}%\n"
             f"EB shrinkage: $-${shrink['shrunk_beats_raw']*100:.1f}% RMSE\n"
             f"League mean: $-${shrink['league_mean_beats_raw']*100:.1f}% RMSE",
             fontsize=6.2, bbox={"boxstyle": "round,pad=0.25", "facecolor": "#F8F9FA", "edgecolor": SLATE, "alpha": 0.94})
    ax1.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="lower right", fontsize=6.2)

    # Panel B: 31 extreme 4-match openings (<= 0.292) across 11 European leagues vs rest of season
    ext = openings["extreme"]
    x_open = [d["index_open"] for d in ext]
    y_rest = [d["index_rest"] for d in ext]
    ax2.axhline(1.0, color="#333333", linestyle=":", linewidth=0.9, label="Season expectation (1.00)")
    ax2.axhline(openings["extreme_rest_median"], color=NAVY, linestyle="--", linewidth=1.3,
                label=f"Bottom-1% rest median ({openings['extreme_rest_median']:.3f}, $n=31$)")
    ax2.axhline(openings["lowest_full_season"]["index"], color=CORAL, linestyle="-.", linewidth=1.1,
                label=f"25-yr archive floor (Celtic {openings['lowest_full_season']['index']:.3f})")
    ax2.scatter(x_open, y_rest, color=TEAL, edgecolor=NAVY, s=26, alpha=0.85,
                label="Bottom 1% openings across Europe ($N=3,100$)")

    # Annotate notable European clubs in the 31 extreme openings
    callouts = [
        ("Norwich (E0)", 0.0, 1.173, (5, 1)),
        ("Celtic (SC0)", 0.0, 0.965, (5, -6)),
        ("Feyenoord (N1)", 0.0, 0.824, (5, -5)),
        ("Galatasaray (T1)", 0.098, 1.083, (-48, 3)),
        ("Las Palmas (SP1)", 0.117, 1.459, (5, 1)),
        ("Chelsea (E0)", 0.174, 1.166, (5, 3)),
        ("Leicester (E0)", 0.200, 0.663, (5, -4)),
    ]
    for name, xo, yr, offset in callouts:
        ax2.annotate(name, (xo, yr), xytext=offset, textcoords="offset points", fontsize=5.6, color=NAVY)

    ax2.set_xlabel("Opening 4-match booking index")
    ax2.set_ylabel("Rest-of-season booking index (matches 5+)")
    ax2.set_title("(b) Reversion of Extreme European Openings ($N = 3,100$)")
    ax2.set_xlim(-0.02, 0.325)
    ax2.set_ylim(0.45, 2.15)
    ax2.legend(frameon=True, facecolor="white", framealpha=0.94, edgecolor="#CBD5E1", loc="upper right", fontsize=5.8)

    fig.savefig(OUT / "fig4.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_fig1()
    make_fig2()
    make_fig3()
    make_fig4()
    for p in sorted(OUT.glob("fig*.pdf")):
        print(f"wrote {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
