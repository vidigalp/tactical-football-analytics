# The season in progress

Regenerated every Tuesday by [`.github/workflows/update.yml`](../.github/workflows/update.yml)
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

**`cards_per_foul`** (league and club, current and history) is yellow cards plus red cards over
fouls committed, as football-data records them. **`cum_cards_per_foul`** is the same rate after
each match: a field of every `by_match` row in the current season, and a list aligned with
`cum_index` for a completed season. It is a description, not a model output: no expectation, no
interval, and it is read against the league rate on the same axis. football-data has no
second-yellow column, so a second-yellow dismissal is one card in England and Scotland and two
elsewhere (see `DATA_SOURCES.md`); yellows also include dissent and bench cards, which have no
foul under them. A club with no fouls yet has no rate (`null`). One team-match in the history
(Alanyaspor, Turkey 2018-19) has no red count and contributes zero reds.

**`display_name`** (club, current and history) is the club's own name. The key beside it is the
name football-data.co.uk uses, and that stays the identity: it keys these files, joins the referee
table, and is what the site's club filter carries in a URL, so it must not be renamed. Only the
label changes. The mapping lives in `data/club_names.csv` and is repeated in `meta.club_names` for
labels drawn outside a club block. A club with no row there is labelled with the source name, so
the field is always present and never empty. Portugal is mapped; the other ten leagues still fall
back to source names.

**`club_colours`** (`meta.json`) gives a series colour for the few clubs whose colour a reader
already knows, keyed like `club_names`. Only clubs whose traditional colour is unambiguous and
unique in their league carry one (Portugal: Benfica, Porto, Sporting); every other club is absent
and the site keeps its own slot colours. Colour alone must never carry the distinction: the site
also varies marker shape, because the red and green here are one hue apart for a colour-blind
reader. The shades are readable on both site themes, not brand assets.

**`fouls_per_card`** (league and club, current and history) is the same ratio inverted, for
reading one club on its own: "one card every 6.3 fouls" instead of "0.159 cards per foul". It is
computed from the counts rather than from the rounded rate, and it is a season total with no
cumulative or by-matchweek version, on purpose. The inverted form is undefined when a club has no
cards (`null`), and it does not preserve the spacing between clubs: three clubs evenly stepped in
`cards_per_foul` are not evenly stepped in `fouls_per_card`, and the distortion always flatters
whichever club is the extreme. Use it to read one number, never to compare, rank or plot.

**`location_sensitivity`** (`meta.json`) is how far foul location alone could move any club's
expected count: multiply expected yellows by `low` for a club whose every foul fell in the
attacking fifth, by `high` for one whose every foul fell in its own fifth. The numbers are study
03's fifth rates over its base rate, read from that study's `facts.json` so they cannot drift
from it, and `own_third_share_r2` is the share of between-club spread in card rate per foul that
own-third share explains there. It is a bound from another dataset, not an adjustment: the feed
has no foul location, and no club's real mix is near either end. Card type has no such bound.

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

## Checking

`tests/test_dashboard_recompute.py` rebuilds every count, expectation, interval, p-value,
percentile and pool from the raw parquet files using only the constants published in `meta.json`,
with none of the code that wrote the files, and fails the weekly run if anything disagrees beyond
the rounding in the files. Nothing in this directory reaches the site without passing it.
