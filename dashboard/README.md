# The season in progress

Regenerated every Monday by [`.github/workflows/update.yml`](../.github/workflows/update.yml)
from the newest snapshot in `data/snapshots/`, by
[`scripts/season_dashboard.py`](../scripts/season_dashboard.py). The site copies these files out
of its `content` submodule at build time and serves them same-origin. Nothing here is a claim;
the studies and the live page are, and they are not rebuilt by the workflow.

The model is the one frozen in the pre-registration of 2026-08-30 and used on the live page,
generalised to eleven leagues. `tests/test_dashboard.py` asserts that the Portuguese coefficients
in `meta.json` are the frozen ones.

## Files

| File | What it holds | Size |
|---|---|---|
| `meta.json` | Snapshot, generation time, every league's model, situation multipliers and shrinkage prior, sources, caveats | ~12 KB |
| `current.json` | Every club in the season in progress with every match played and the cumulative index after each, percentiles, and the Europe-wide same-matchweek distribution | ~200 KB |
| `history/{league}.json` | Every completed season of one league: club-season totals, index, interval, shrunk estimate, cumulative index by matchweek, league rates by matchweek, and the league's same-matchweek distribution | 60 to 330 KB |

Season codes are football-data's: `2627` is 2026-27. Club names are football-data's too and are
stable within a league across seasons.

## Fields worth knowing

**`index`** is yellow cards observed over yellow cards expected. Expected is `intercept + slope ×
fouls` times the situation multiplier for the club's pre-match strength band. 1.0 is as expected.
`lo` and `hi` are the exact 95% Poisson interval on the count. Intervals are the point of the
dataset: early in a season they admit almost anything.

**`shrunk`, `shrunk_lo`, `shrunk_hi`, `reliability`** come from study 04's gamma-Poisson prior,
fitted on the league's completed club-seasons. `reliability` is the share of the observed
deviation that survives shrinkage. In most leagues it is small even for a full season, which is
study 04's finding and not a defect.

**`league_percentile`** and **`europe_percentile`** are the share of clubs this season, in the
league and across all eleven leagues, at or below this club's index.
**`league_history_percentile`** and **`europe_history_percentile`** are the same against every
completed team-season cut at the same number of matches. These say where a club sits among clubs
measured the same way. They are not a ranking, and a list sorted on them would be one.

**`p`, `bh`, `survives_bh`**: two-sided Poisson p, its Benjamini-Hochberg adjustment across the
league's clubs, and whether it clears FDR 0.10. Surviving the screen is the minimum for a club to
be worth a second look, not a finding.

**`by_match`** (current) carries every match with its own counts, band and expectation, and the
cumulative index and interval after it. **`cum_index`** (history) is the same trajectory for a
completed season, as a list indexed by match number.

**`by_matchweek`** (league level, current and history) gives cumulative yellows per match, fouls
per match, reds per match and cards per foul after every club's k-th match, so a season can be read
against earlier seasons at the same point. Per match means both sides counted: a league at 4.7
yellows per match is booking about 2.3 per team.

**`cum_index_by_matchweek`** (history, per league) and **`europe_cum_index_by_matchweek`**
(current) are the 5th, 25th, 50th, 75th and 95th percentiles of the cumulative index across every
completed team-season after k matches, with `n`, the size of that pool. The pool is every
completed team-season up to k = 30 and shrinks past it, since seasons run 30 to 38 matches. A
current trajectory drawn over this band is the honest version of "outlier or noise".

**`band_summary`** (history, per league) and **`europe_band_summary`** (current) say how often a
completed team-season leaves that 5th-95th band: `ever_outside_pct` at any point in the season,
`outside_at_end_pct` at its last match, over `team_seasons`. About a tenth end outside by
construction; the share that visits the outside at some point is between 43% and 55% depending on
the league, and it is not "most", which is why the number is in the file.
