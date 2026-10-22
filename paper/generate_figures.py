"""Generate the four publication-grade vector figures for the consolidated paper.

Reads exclusively from committed JSON sidecars and Parquet artifacts in the repository.
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
    "font.size": 8.5,
    "axes.titlesize": 8.6,
    "axes.titleweight": "bold",
    "axes.labelsize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.2,
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
    ref_table = json.loads((ROOT / "reports/02-fouling-with-impunity/referee_table.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.35), constrained_layout=True)

    # Panel A: Pre-match expectation band across 11 leagues + Portugal highlight
    bands = ["heavy favourite", "favourite", "even", "underdog", "heavy underdog"]
    labels = ["Heavy\nFav.", "Fav.", "Even", "Under-\ndog", "Heavy\nUnd."]
    x = np.arange(len(bands))
    by_lg = story["all_leagues"]["by_league"]
    for lg, vals in by_lg.items():
        y = [vals[b] for b in bands]
        ax1.plot(x, y, color=SLATE, alpha=0.28, linewidth=1.0)
    p1_y = [by_lg["P1"][b] for b in bands]
    med_y = [np.median([by_lg[lg][b] for lg in by_lg]) for b in bands]
    ax1.plot(x, med_y, color=NAVY, marker="o", linewidth=2.0, markersize=4.5,
             label="11-league median (0.856 to 1.098)")
    ax1.plot(x, p1_y, color=CORAL, marker="s", linewidth=1.8, markersize=4.5,
             linestyle="--", label="Portugal P1 (0.854 to 1.121)")
    ax1.axhline(1.0, color="#333333", linestyle=":", linewidth=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Yellow cards / expected from fouls")
    ax1.set_title("(a) Expectation Gradient (11 Leagues)")
    ax1.set_ylim(0.74, 1.20)
    ax1.legend(frameon=False, loc="upper left")

    # Panel B: Raw vs Referee+Situation Adjusted Booking Index in Portugal
    highlight_clubs = ["Sp Lisbon", "Boavista", "Sp Braga", "Porto", "Benfica", "Gil Vicente"]
    display_names = ["Sporting CP*", "Boavista", "SC Braga", "FC Porto", "SL Benfica", "Gil Vicente"]
    y_pos = np.arange(len(highlight_clubs))[::-1]
    tbl = ref_table["table"]

    raw_vals = [tbl[c]["raw"] for c in highlight_clubs]
    adj_vals = [tbl[c]["referee"] for c in highlight_clubs]
    lo_vals = [tbl[c]["lo"] for c in highlight_clubs]
    hi_vals = [tbl[c]["hi"] for c in highlight_clubs]

    ax2.axvline(1.0, color="#333333", linestyle=":", linewidth=0.9)
    for i, (r_v, a_v, lo, hi) in enumerate(zip(raw_vals, adj_vals, lo_vals, hi_vals)):
        yp = y_pos[i]
        ax2.plot([r_v, a_v], [yp, yp], color=SLATE, linewidth=1.0, zorder=1)
        ax2.errorbar(a_v, yp, xerr=[[a_v - lo], [hi - a_v]], fmt="none",
                     ecolor=NAVY, elinewidth=1.4, capsize=2.5, zorder=2)
    ax2.scatter(raw_vals, y_pos, color="white", edgecolor=CORAL, s=36, linewidth=1.5,
                zorder=3, label="Raw booking index")
    ax2.scatter(adj_vals, y_pos, color=NAVY, s=36, zorder=4,
                label="Adjusted (era + strength + referee)")
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(display_names)
    ax2.set_xlabel("Booking index (observed / expected yellows)")
    ax2.set_title("(b) Deconfounded Portuguese Clubs")
    ax2.set_xlim(0.78, 1.32)
    ax2.legend(frameon=False, loc="lower right")

    fig.savefig(OUT / "fig1.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig2() -> None:
    story = json.loads((ROOT / "reports/02-fouling-with-impunity/story.json").read_text())
    agg = json.loads((ROOT / "reports/02-fouling-with-impunity/aggregation.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.3), constrained_layout=True)

    # Panel A: Yellows per foul vs foul count
    ypf = story["yellows_per_foul"]
    f_bins = sorted((float(k), float(v)) for k, v in ypf.items())
    fx = [k for k, _ in f_bins]
    fy = [v for _, v in f_bins]
    ax1.plot(fx, fy, color=NAVY, marker="o", linewidth=2.0, markersize=4.5,
             label="Observed yellows / foul")
    # Affine fit illustration: E[Y]/F = a/F + b
    f_grid = np.linspace(4.8, 24.0, 100)
    # Least-squares fit to bin points of y*f = a + b*f
    y_tot = np.array([k * v for k, v in f_bins])
    A = np.column_stack([np.ones(len(fx)), fx])
    a_hat, b_hat = np.linalg.lstsq(A, y_tot, rcond=None)[0]
    ax1.plot(f_grid, (a_hat + b_hat * f_grid) / f_grid, color=CORAL, linestyle="--",
             linewidth=1.5, label=f"Affine fit ($a={a_hat:.2f}, b={b_hat:.3f}$)")
    ax1.axhline(np.mean(fy), color=SLATE, linestyle=":", linewidth=1.1,
                label="Proportional assumption ($a=0$)")
    ax1.set_xlabel("Team fouls committed in match")
    ax1.set_ylabel("Observed yellow cards per foul")
    ax1.set_title("(a) Non-Foul Intercept Dilution (0.197 to 0.122)")
    ax1.legend(frameon=False, loc="upper right")

    # Panel B: Multi-level aggregation reversal
    g_by_lg = agg["gradient_by_league"]
    lgs = sorted(g_by_lg.keys())
    h_gd = [g_by_lg[k]["home_gd"] for k in lgs]
    grad = [abs(g_by_lg[k]["gradient"]) for k in lgs]
    ax2.scatter(h_gd, grad, color=NAVY, s=36, zorder=3)
    for k, x_v, y_v in zip(lgs, h_gd, grad):
        ax2.annotate(k, (x_v, y_v), xytext=(3, 2), textcoords="offset points", fontsize=6.8)
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
    ax2.legend(frameon=False, loc="upper right", fontsize=6.8)

    fig.savefig(OUT / "fig2.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig3() -> None:
    chart = json.loads((ROOT / "reports/03-the-lever-nobody-pulls/chart.json").read_text())
    facts = json.loads((ROOT / "reports/03-the-lever-nobody-pulls/facts.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.3), constrained_layout=True)

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
    ax1.legend(frameon=False, loc="upper right", fontsize=6.9)

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
                label=f"Late close-score window ({facts['tactical_window_rate']*100:.1f}%, R²=0.3%)")
    ax2.annotate("Half-time reset:\n16.1% (40-45') -> 12.8% (45-50')\n(p = 4e-4)",
                 xy=(2.5, 14.5), xytext=(1.2, 20.5),
                 arrowprops={"arrowstyle": "->", "color": NAVY, "lw": 0.9},
                 fontsize=6.8, color=NAVY)
    ax2.set_xticks(mx)
    ax2.set_xticklabels(m_labels)
    ax2.set_xlabel("Match minute band")
    ax2.set_ylabel("Card probability per foul (%)")
    ax2.set_title("(b) Temporal Escalation & Situational Window")
    ax2.set_ylim(4, 30)
    ax2.legend(frameon=False, loc="upper left", fontsize=6.9)

    fig.savefig(OUT / "fig3.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig4() -> None:
    pers = json.loads((ROOT / "reports/04-how-much-of-an-index-is-real/persistence.json").read_text())
    shrink = json.loads((ROOT / "reports/04-how-much-of-an-index-is-real/shrinkage.json").read_text())
    openings = json.loads((ROOT / "reports/live-season-portugal/openings.json").read_text())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.3), constrained_layout=True)

    # Panel A: Per-league persistence r across 11 leagues vs matched Poisson null
    per_lg = sorted(pers["per_league"], key=lambda d: d["r"])
    lgs = [d["lg"] for d in per_lg]
    rs = [d["r"] for d in per_lg]
    y_pos = np.arange(len(lgs))

    ax1.axvspan(-pers["null_r_max"], pers["null_r_max"], color=LIGHT_GREY, zorder=1,
                label=f"Matched Poisson null max (+{pers['null_r_max']:.3f})")
    ax1.barh(y_pos, rs, color=NAVY, height=0.62, alpha=0.85, zorder=2)
    ax1.axvline(pers["r"], color=CORAL, linestyle="--", linewidth=1.5, zorder=3,
                label=f"Pooled within-league r = +{pers['r']:.3f}")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(lgs)
    ax1.set_xlabel("Year-to-year club booking index correlation (r)")
    ax1.set_title("(a) Persistence Across 11 Leagues (N = 2,528)")
    ax1.set_xlim(-0.08, 0.48)
    ax1.text(0.18, 1.3,
             f"True variance share: {pers['true_share']*100:.1f}%\n"
             f"EB shrinkage beats raw: -{shrink['shrunk_beats_raw']*100:.1f}% RMSE\n"
             f"League mean beats raw: -{shrink['league_mean_beats_raw']*100:.1f}% RMSE",
             fontsize=6.7, bbox={"boxstyle": "round,pad=0.3", "facecolor": "#F8F9FA", "edgecolor": SLATE})
    ax1.legend(frameon=False, loc="lower right", fontsize=6.8)

    # Panel B: 31 extreme 4-match openings (<= 0.292) vs rest of season
    ext = openings["extreme"]
    x_open = [d["index_open"] for d in ext]
    y_rest = [d["index_rest"] for d in ext]
    ax2.axhline(1.0, color="#333333", linestyle=":", linewidth=0.9, label="Season expectation (1.00)")
    ax2.axhline(openings["extreme_rest_median"], color=NAVY, linestyle="--", linewidth=1.3,
                label=f"Extreme-31 rest median ({openings['extreme_rest_median']:.3f})")
    ax2.axhline(openings["lowest_full_season"]["index"], color=CORAL, linestyle="-.", linewidth=1.1,
                label=f"25-yr archive floor (Celtic {openings['lowest_full_season']['index']:.3f})")
    ax2.scatter(x_open, y_rest, color=TEAL, edgecolor=NAVY, s=28, alpha=0.85,
                label="Bottom 1% 4-match openings (n = 31)")
    ax2.axvline(openings["club_index_open"], color=AMBER, linewidth=1.4,
                label=f"Live case 4-match opening ({openings['club_index_open']:.3f})")
    ax2.set_xlabel("Opening 4-match booking index")
    ax2.set_ylabel("Rest-of-season booking index (matches 5+)")
    ax2.set_title("(b) Reversion of Extreme Openings (N = 3,100)")
    ax2.set_xlim(-0.02, 0.31)
    ax2.set_ylim(0.45, 1.55)
    ax2.legend(frameon=False, loc="lower right", fontsize=6.4)

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
