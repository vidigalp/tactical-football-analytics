# A club that fouls with impunity, and the four ways I was wrong about it

**Published:** 2026-08-30 · **Data:** `2026-W35`, with the season in progress from `2026-W36` · **Claim level:** L2 (hypothesis, adjusted)

---

## What the data says

Across eleven European leagues (58,013 completed matches, 115,984 team-matches, and 246 clubs with
150+ matches), raw yellow-cards-per-foul ratios make almost every dominant domestic club in Europe
appear leniently officiated (**r = −0.371**). That apparent impunity is a compound artifact of
three confounders: pre-match win expectation (**1.098** heavy underdog vs. **0.856** heavy
favourite median across all eleven leagues), non-foul conduct cards (dissent, delaying restarts,
simulation) entering as a positive affine intercept (**11.1%–38.8%** league-mean share; **13%–47%**
across league-seasons), and fixture-level competitive intensity shared by both teams on the pitch
(**r = +0.283** on opponents' booking indices; **11 of 11** leagues rising across opponent-strength
terciles **0.938** to **0.993** to **1.088**).

Adjusting for single-match win expectation alone removes the favourite discount (**1.098** vs.
**0.856**) but overshoots for elite clubs (**r = +0.484**) unless fixture quality is also accounted
for. Netting out both the affine intercept and both teams' fixture quality ($I^{\text{fix}}_i$)
eliminates the residual strength gradient across all 246 European clubs (**r = +0.095**, **p =
0.139**), equalises the top and bottom strength quartiles (**1.012** vs. **1.013**, **p = 0.917**),
and pulls Europe's perennial domestic champions — Olympiacos (**0.767** raw to **0.920**), Celtic
(**0.828** to **0.996**), Club Brugge (**0.878** to **1.002**), SL Benfica (**0.885** to **0.976**),
FC Porto (**0.890** to **1.031**, and **1.002** after referee adjustment), Juventus (**0.907** to
**1.002**), Feyenoord (**0.918** to **0.973**), Bayern Munich (**0.940** to **1.021**), Inter
(**0.944** to **0.991**), PSV (**0.944** to **1.028**), Barcelona (**0.967** to **1.010**),
Galatasaray (**0.975** to **1.036**), Real Madrid (**0.977** to **1.023**), Manchester City
(**1.000** to **1.029**), and Arsenal (**1.005** to **1.027**) — onto parity (**≈ 1.00**), leaving
**23 of 246** clubs (**9.3%**) separating under universe-wide Benjamini–Hochberg FDR (**q < 0.10**).

In the Portuguese league, once you account for pre-match role, era, and the referee who was
actually appointed (part of a three-league, 80-club leave-one-club-out referee decomposition across
**35,844** team-matches and **392** officials where every club's referee draw sits within
**[0.971, 1.021]**, RMS shift **0.0085**), one club of twenty-six is booked measurably more than
expected. It is Sporting, at 1.18 (**1.177** referee-adjusted, **1.117** fixture-adjusted). Porto
and Benfica both sit at 1.00 (**1.002**), indistinguishable from average.

A post had gone around implying Porto were being favoured by referees. That is where the question
came from, and it is the last time the post appears here. The claim is the object of study; the
person who made it is not, so it is neither linked nor named. See [`EDITORIAL.md`](../../EDITORIAL.md).

## The pre-registered question

> Is there a measurable difference in how often a given club is booked, relative to the fouls it
> commits?

Written before the data was pulled. What follows reports what happened, including the parts where
the answer changed under its own tests.

## The metric

**Booking index** `LITERATURE-adjacent, COINED in this form`. Yellow cards received, divided by
yellow cards expected from the team's own foul count. An index of 1.0 means booked exactly as
often as the fouls imply.

The underlying quantity — cards conditioned on fouls — is standard. Phatak et al. (2021) use
fouls-per-card across five leagues. The name and the specific expectation model here are mine, and
neither appears in the literature under this label. Treating it as an established measure would be
a mistake.

## The first answer, which looked good and was wrong

Porto's raw booking index comes out at **0.890**. Comfortably below 1.0, interval excluding it.
Benfica sits at **0.885**. On its face, two clubs booked around 12% less than their fouls imply.

Nor is that pattern peculiar to Portugal. Across all **246 European clubs** with 150+ matches in
our eleven-league archive, the raw proportional booking index ($I^{\text{raw}}_i$) correlates
negatively with club strength at **r = −0.371**: the top strength quartile (62 clubs) averages
**0.971** against **1.026** for the bottom quartile, and the 26 elite domestic title contenders
($\bar{s}_i \ge 1.0$) average **0.949** (median **0.944**). Nearly every perennial domestic
champion in Europe sits below 1.00 on raw cards per foul: Olympiacos (**0.767**), Celtic
(**0.828**), Liverpool (**0.876**), Club Brugge (**0.878**), SL Benfica (**0.885**), FC Porto
(**0.890**), Juventus (**0.907**), Feyenoord (**0.918**), Borussia Dortmund (**0.920**), Rangers
(**0.939**), Bayern Munich (**0.940**), Inter (**0.944**), PSV (**0.944**), Ajax (**0.953**),
Barcelona (**0.967**), Galatasaray (**0.975**), and Real Madrid (**0.977**).

That is roughly the shape the original claim predicted. It is also wrong three times over.

## Wrong (1): most of it is being the favourite

![Context effect](figures/fig1-context-effect.png)

Booking rate per foul depends heavily on how strong you were expected to be in that specific
match. In Portugal, the league the question was about and the one the figure shows, a heavy
underdog is booked at **1.121** times its foul count and a heavy favourite at **0.854**. A 31%
swing, with no club identity involved.

![The same gradient in every league](figures/fig2-context-all-leagues.png)

The pattern is not Portuguese. The underdog end sits above the favourite end in **all eleven
leagues**, median **1.098** against **0.856** (spanning from **0.907** to **1.038** in Spain to
**0.802** to **1.157** in Scotland and **0.778** to **1.158** in Greece). Per-league bands are in
[`story.json`](story.json), alongside every other number this study's figures carry.

Strict monotonicity across all five bands holds in seven of them. Germany, France, Italy and Spain
each tick up by less than 0.01 between the two underdog bands, which are also their smallest
samples. The direction is everywhere; the perfectly clean staircase is not.

Dominant clubs are favourites most weeks. So roughly half of Porto's apparent leniency was being
the better side, which they share with every strong club in Europe.

## Wrong (2): the expectation model was misspecified

The expectation assumed yellow cards are proportional to fouls: *expected = rate × fouls*. They are not.

![Yellows per foul against foul count](figures/fig3-yellows-per-foul.png)

Fitting `yellows = a + b × fouls` per league-season gives a positive intercept worth **11.1% to
38.8%** of league-mean yellow cards (**11.1%** in England, **18.5%** in Germany, **22.2%** in
France, **30.2%** in Spain, **32.3%** in Italy, **38.2%** in Portugal, and **38.8%** in Greece,
with median **22.2%** across the eleven leagues; **13% to 47%** across individual league-seasons).
Observed yellows per foul falls monotonically across the range, from **0.197** in matches where a
side commits six fouls or fewer (**5.1** bin mean) to **0.122** where it commits more than twenty
(**23.4** bin mean). Every bin is in [`story.json`](story.json).

That intercept is interpretable. It is the cards that have nothing to do with your foul count:
dissent, delaying the restart, entering the field of play, simulation, plus whatever the data feed
does or does not record as a foul. In Greece, Portugal, and Italy it is roughly a third to two
fifths of all cards.

Forcing the line through the origin inflates every low-foul team and deflates every high-foul team,
with no behaviour involved. A test on synthetic teams with identical card processes shows the
proportional model inventing a gap of over 0.10 between them.

Dominant clubs foul less than average. The model was flattering exactly the clubs the finding was
about.

## Wrong (3): the effect is not the club's — and netting out fixture quality eliminates the gradient

Adjusting for single-match win expectation removes the favourite discount (**1.098** vs. **0.856**),
but across the 246-club European universe it overshoots for elite clubs: the correlation with club
strength flips positive to **r = +0.403** on five strength bands and **r = +0.484** (Spearman
**+0.349**, positive in **11 of 11** leagues; top vs. bottom quartile **1.048** vs. **0.984**) on a
continuous quartic Poisson fit.

Why do dominant clubs appear to be booked *more* than expected once single-match win probability is
controlled for? The test that answers this is embarrassingly cheap: compute the same adjusted
index for each club's **opponents** in the matches played against that club.

| | |
|---|---|
| corr(club strength, **own** role-adjusted index) | **+0.484** |
| corr(club strength, **opponents'** role-adjusted index) | **+0.283** (p = 7×10⁻⁶) |
| corr(own index, opponents' index) | +0.116 (p = 0.07) |
| corr(club strength, **affine + fixture-adjusted** index $I^{\text{fix}}_i$) | **+0.095** (p = 0.139) |

All four from `scripts/strength_effect.py`, recorded in
[`strength_effect.json`](strength_effect.json).

When a dominant club plays, the other team is booked more per foul too, and the two are close to
independent. A club-level story predicts the second correlation is zero. It is not.

The within-club version is cleaner still. Holding the club fixed and splitting its own matches by
opponent quality:

![Booking index by opponent quality](figures/fig4-opponent-test.png)

| Opponent | Portugal | Median of eleven leagues |
|---|---|---|
| Weakest third | 0.939 | 0.938 |
| Middle third | 0.973 | 0.993 |
| **Strongest third** | **1.092** | **1.088** |

It rises in **11 of 11** leagues. Club identity is differenced out here, so this is the same side,
playing the same way, booked differently according to who is at the other end of it.

So the correct statement is not *"dominant clubs are booked more."* It is:

> Yellows per foul scale with the quality of the fixture, for both teams.

A club's own quality is half of that fixture quality, so strong clubs genuinely do see a higher
rate. They are not being singled out. They are playing in higher-quality matches, and those
matches produce more yellows per foul.

### Deconfounding the 246-club European universe ($I^{\text{fix}}_i$)

Once we net out **both the affine non-foul intercept and both clubs' season strengths**
($\bar{s}_{i,s}, \bar{s}_{j,s}$) alongside single-match role ($s_{i,m}$) in the Poisson expectation
model ($I^{\text{fix}}_i$), the over-correction disappears across all **246 European clubs**:

- The residual correlation between club strength and the booking index drops from **+0.484** to
  **r = +0.095** (**p = 0.139**).
- The top and bottom strength quartiles become indistinguishable (**1.012** vs. **1.013**, two-sample
  *t*-test **p = 0.917**), and the 26 elite title contenders ($\bar{s}_i \ge 1.0$) sit at a mean of
  **1.031** (median **1.029**).
- Perennial domestic champions across Europe that looked lenient on raw ratios ($I^{\text{raw}}_i < 1.00$),
  as well as elite clubs like Manchester City (**1.000** raw to **1.076** role / **1.072** referee),
  Arsenal (**1.005** to **1.095** / **1.093**), and Rangers (**0.939** to **1.098** / **1.100**) that
  looked artificially elevated under single-match role adjustment because their fixtures are
  high-intensity contests, collapse onto statistical parity ($I^{\text{fix}}_i \approx 1.00$, all
  Benjamini–Hochberg $q_{\text{univ}} > 0.10$):

![European champions and outliers before and after fixture adjustment](figures/fig8-european-champions-adjusted.png)

| League | Club | Matches | Strength $\bar{s}_i$ | Raw $I^{\text{raw}}_i$ | Affine $I^{\text{aff}}_i$ | Role Adj. $I^{\text{sit}}_i$ | Fixture Adj. $I^{\text{fix}}_i$ | 95% Poisson CI | BH $q_{\text{univ}}$ |
|---|---|---|---|---|---|---|---|---|---|
| `G1` | Olympiacos | 243 | +1.552 | 0.767 | 0.751 | 0.905 | **0.920** | [0.837, 1.008] | 0.313 |
| `SC0` | Celtic | 937 | +1.946 | 0.828 | 0.814 | 1.005 | **0.996** | [0.939, 1.055] | 0.975 |
| `B1` | Club Brugge | 251 | +1.315 | 0.878 | 0.863 | 1.028 | **1.002** | [0.905, 1.106] | 0.995 |
| `P1` | SL Benfica | 306 | +1.935 | 0.885 | 0.850 | 1.009 | **0.976** | [0.901, 1.055] | 0.795 |
| `P1` | FC Porto | 306 | +1.941 | 0.890 | 0.893 | 1.018 | **1.031** | [0.956, 1.110] | 0.745 |
| `I1` | Juventus | 758 | +1.315 | 0.907 | 0.900 | 0.999 | **1.002** | [0.952, 1.054] | 0.993 |
| `N1` | Feyenoord | 297 | +1.346 | 0.918 | 0.908 | 1.004 | **0.973** | [0.877, 1.076] | 0.820 |
| `D1` | Borussia Dortmund | 836 | +0.847 | 0.920 | 0.905 | 0.977 | **0.940** | [0.889, 0.992] | 0.157 |
| `SC0` | Rangers | 781 | +1.568 | 0.939 | 0.932 | 1.098 | **1.066** | [1.006, 1.128] | 0.176 |
| `D1` | Bayern Munich | 836 | +1.799 | 0.940 | 0.907 | 1.060 | **1.021** | [0.965, 1.079] | 0.753 |
| `I1` | Inter | 798 | +1.133 | 0.944 | 0.917 | 1.025 | **0.991** | [0.942, 1.042] | 0.885 |
| `N1` | PSV Eindhoven | 298 | +1.691 | 0.944 | 0.929 | 1.051 | **1.028** | [0.927, 1.138] | 0.819 |
| `N1` | Ajax | 297 | +1.828 | 0.953 | 0.943 | 1.063 | **1.078** | [0.974, 1.190] | 0.471 |
| `SP1` | Barcelona | 798 | +1.859 | 0.967 | 0.897 | 1.047 | **1.010** | [0.960, 1.061] | 0.856 |
| `T1` | Galatasaray | 321 | +1.187 | 0.975 | 0.968 | 1.067 | **1.036** | [0.961, 1.115] | 0.712 |
| `SP1` | Real Madrid | 798 | +1.611 | 0.977 | 0.937 | 1.047 | **1.023** | [0.975, 1.073] | 0.710 |
| `E0` | Manchester City | 941 | +1.054 | 1.000 | 0.985 | 1.076 | **1.029** | [0.977, 1.084] | 0.631 |
| `E0` | Arsenal | 977 | +1.081 | 1.005 | 0.997 | 1.095 | **1.027** | [0.976, 1.080] | 0.655 |

Across all 246 clubs, universe-wide Benjamini–Hochberg FDR control at $q < 0.10$ leaves **23 of
246** clubs (**9.3%**) separating from 1.00 (26 under within-league BH, down from 47 on raw ratios
and 30 on role-only adjustment): 10 high-booking clubs led by Union SG (`B1`, **1.228**), AC
Ajaccio (`F1`, **1.163**), SC Bastia (`F1`, **1.150**), Sporting CP (`P1`, **1.117** fixture /
**1.177** referee-adjusted), Chelsea (`E0`, **1.112** fixture / **1.178** referee-adjusted),
Boavista (`P1`, **1.101**), Getafe (`SP1`, **1.089**), Sunderland (`E0`, **1.087**), Roma (`I1`,
**1.068**), and Lazio (`I1`, **1.067**); and 13 low-booking clubs led by Heerenveen (`N1`,
**0.845**), Real Sociedad (`SP1`, **0.877**), PAS Lamia (`G1`, **0.880**), Gil Vicente (`P1`,
**0.887**), Liverpool (`E0`, **0.894**), Southampton (`E0`, **0.894**), and SC Freiburg (`D1`,
**0.894**). All 246 club records are in [`strength_effect.json`](strength_effect.json).

## If not the club, then the manager?

![Manager travel](figures/fig5-manager-travel.png)

The natural next candidate. Managers set how a side presses and how it fouls, and Portuguese clubs
change them often enough to test it: take every manager who worked at two or more clubs, measure
each spell against that club's own baseline excluding them, and see whether the two spells agree.

They do not. Across 42 spell pairs the correlation is **r = −0.076**, and a permutation test that
reshuffles which spell belongs to which manager gives **p = 0.628**. The observed value sits in the
middle of the null. A manager who runs a disciplined side at one club is no more likely than chance
to do it at the next.

Between-manager variance accounts for about 12% of the spread in spell effects, which is small
enough that the honest reading is that this data cannot see a manager effect, rather than that none
exists. Either way, the club-level story does not become a manager-level story. Every number in this
section is in [`manager_travel.json`](manager_travel.json).

## Wrong (4), sort of: someone got there first

Dawson, Dobson, Goddard and Wilson published a gradient in cards by team strength in 2007
(*JRSS-A* 170(1)), on 2,660 Premier League matches, with a Nash-equilibrium model of aggression.
Their reduced form is a subset of the one used here.

What may be new is conditioning on fouls: asking not "who gets more cards" but "who gets more
cards for the same number of fouls". Rediscovering a known result on twenty-two times the data is
worth doing. Presenting it as new is not.

## So: was the club being favoured?

On this measure, no.

Portugal has no referee data in the standard source, so we assembled it: 2,737 match-official rows
across ten seasons, 98.4% joined to our matches and validated on scorelines rather than names.
Together with England (`E0`) and Scotland (`SC0`), where match officials are named continuously in
the primary archive, that gives **35,844** referee-tracked team-matches across **392** referees
(**144** with 40+ matches) and **80** clubs, recorded in
[`referee_decomposition.json`](referee_decomposition.json) by `scripts/referee_decomposition.py`:

| League | Team-matches | Officials (40+ matches) | Referee multiplier range | Clubs ranked | Club referee draw range | RMS referee shift |
|---|---|---|---|---|---|---|
| England (`E0`) | 19,580 | 61 / 181 | 0.593 to 1.193 (spread 0.600) | 36 | [0.979, 1.019] | 0.007 |
| Scotland (`SC0`) | 10,756 | 51 / 160 | 0.662 to 1.206 (spread 0.544) | 18 | [0.996, 1.013] | 0.006 |
| Portugal (`P1`) | 5,508 | 32 / 51 | 0.755 to 1.324 (spread 0.569) | 26 | [0.971, 1.021] | 0.011 |
| **Three-league total** | **35,844** | **144 / 392** | **0.593 to 1.324** | **80** | **[0.971, 1.021]** | **0.0085** |

Each club is judged against officials measured **without** that club (leave-one-club-out).
Otherwise a side that draws one official often helps set the baseline it is being judged against,
and a real effect partly cancels itself. Across all 80 clubs in England, Scotland, and Portugal,
individual referees vary widely (multipliers from 0.593 to 1.324, comparable to the pre-match role
effect), yet long-run club assignments balance out almost completely: every club's leave-one-club-out
mean referee draw falls between **0.971 and 1.021**, moving club booking indices by a
root-mean-square shift of only **0.0085** (**r = +0.990** between situation-adjusted and
referee-adjusted indices).

In Portugal, adjusting for era, match situation and the actual official on the pitch:

| Club | Booking index | 95% interval |
|---|---|---|
| **Sporting** | **1.177** | [1.094, 1.264] |
| Benfica | 1.002 | [0.925, 1.084] |
| Porto | 1.002 | [0.929, 1.079] |

Produced by `scripts/portugal_referee_table.py`, with all 26 clubs in
[`referee_table.json`](referee_table.json).

Porto sit at 1.002, indistinguishable from average. One club of twenty-six separates from
expectation, and it is not the one in the original claim.

![Clubs before and after adjustment](figures/fig6-clubs-adjusted.png)

The figure shows the era-and-situation step only, which is why Porto reads 1.02 there against 1.00
in the table: the referee adjustment moves them slightly further down. The shape is the point.
Almost every club that looked unusual on the raw index stops looking unusual once the situation is
accounted for, and the hollow-to-solid movement is the size of that correction.

### The multiplicity check, which is where most of these die

Testing twenty-six clubs and reporting the extreme one is how you manufacture a finding. One club
clears an uncorrected p < 0.05, and the next two sit just outside it.

Under a Benjamini–Hochberg screen at FDR 0.10, one survives:

| Club | Index | raw p | BH-adjusted | Bonferroni |
|---|---|---|---|---|
| Sporting | 1.177 | 0.00002 | **0.0004** | **0.0004** |
| Gil Vicente | 0.928 | 0.081 | 0.635 | 1.000 |
| Boavista | 1.062 | 0.090 | 0.635 | 1.000 |

These p-values are two-sided, computed by the script alongside the table. They were previously
typed in by hand and cannot be reproduced from any method recorded here, which is why they moved:
the runner-up used to read 0.044 and now reads 0.081. Two-sided is the convention the 95% interval
above already assumes, and no direction was specified in advance for a club sitting *below*
expectation, so the screen and the interval now agree about which clubs are extreme.

Gil Vicente is the one a naive threshold would have published. Sporting survives Bonferroni too,
which is the conservative correction and not one this result needed.

### What this cannot say

It measures yellow cards relative to fouls committed and nothing else. It says nothing about
penalties given or denied, offside calls, disallowed goals, red cards specifically, added time, or
whether any individual decision was correct. If "favoured" means those things, this analysis is
silent on it and should not be quoted as though it were not.

A high index is also not misconduct. Sporting commit fouls that draw cards more often than their
foul count predicts. Why is a separate question this data cannot answer.

## What happens next, and what the index is worth

Two questions this report raises are answered elsewhere, because neither is about Porto.

**The season in progress** has its own page, [the Portuguese season as it
stands](../live-season-portugal/report.md). It is deliberately not part of this report: a live test
with a resolution date in November would leave a dated document permanently unfinished, and the
pre-registration deserves a surface that is expected to change.

**Whether a one-season booking index means anything at all** is [study
04](../04-how-much-of-an-index-is-real/report.md). It has to be asked, because Sporting separating
and Porto not is only interesting if the measure carries a club property in the first place. It
does, and it is small: 15% of the spread between clubs in a season is real and the rest is the
Poisson noise of one season's cards.

## The data lesson

The version that transfers, and the reason this report is in a repository about method rather than
about football: **when a metric is an average over a group, ask whether the effect belongs to the
group or to the situations the group is in.** Cohorts, segments, cost centres, model slices. The
arithmetic is identical and so is the error.

Every attack run against this finding, and the two that killed part of it, are in the table below.

## Pressure tests

`METHODS.md` §11 attacks a finding on six fronts before it is published. The point of tabulating
them is that an attack never tried cannot pass as one tried and survived.

| Attack | Status | What happened |
|---|---|---|
| Specification | **run — landed** | The expectation was `cards = rate x fouls`, proportional through the origin. Measured, the non-foul conduct intercept is 11.1% to 38.8% of league-mean cards (13% to 47% across league-seasons). Because dominant clubs foul *less*, that misspecification inflated exactly the clubs the finding was about. |
| Aggregation | **run — landed** | Recomputed the index for the *opponents*: it correlates with club strength at r = +0.283 and rises across opponent-strength terciles in 11 of 11 leagues (0.938 to 0.993 to 1.088), proving the effect belongs to the fixture. Netting out both the affine intercept and fixture quality ($I^{\text{fix}}_i$) eliminates the residual strength gradient across all 246 clubs (r = +0.095, p = 0.139). |
| Adjustment coarseness | **run — survived** | Five strength bands under-corrected the strongest clubs (r = +0.403); redone as a continuous quartic Poisson fit (r = +0.484) and then augmented with both teams' season strengths ($I^{\text{fix}}_i$, r = +0.095), equalising top and bottom quartiles (1.012 vs. 1.013, p = 0.917). |
| Prior work | **run — landed** | Dawson, Dobson, Goddard and Wilson (2007) published a strength gradient in cards. What may be new here is conditioning on fouls, not the gradient. |
| Baseline sufficiency | **run — survived** | Asked and answered in [study 04](../04-how-much-of-an-index-is-real/report.md), which resamples the booking index from a world where clubs differ in nothing and finds the observed carry-over far outside it. The numbers live there rather than being restated here. |
| Cross-sectional, few units | **run — landed** | The home-advantage explanation correlates at +0.782 across eleven league averages and −0.086 within leagues over time. One dataset, three aggregation levels, and the coarsest one manufactured it. |

Two of the six killed something. Both deaths are in the body of this report rather than in a
footnote, because the deaths are the finding.

## Tri-anchor

| Anchor | Source |
|---|---|
| **Data** | 58,013 completed-season matches across 11 leagues, 2000–2025, committed snapshot `2026-W35`, plus 2,737 Portuguese match officials |
| **Football** | Dawson et al. (2007) on referee inconsistency and the strength gradient; Phatak et al. (2021) on fouls-to-cards across leagues |
| **Data science** | Efron & Morris (1975) on shrinkage; Benjamini & Hochberg (1995) on multiplicity |

## References

- Dawson, P., Dobson, S., Goddard, J. & Wilson, J. (2007). Are Football Referees Really Biased and
  Inconsistent? *JRSS-A* 170(1), 231–250. [doi:10.1111/j.1467-985X.2006.00451.x](https://doi.org/10.1111/j.1467-985X.2006.00451.x)
- Phatak, A., Rein, R. & Memmert, D. (2021). The Dirty League. *J. Human Kinetics* 80, 263–276.
  [doi:10.2478/hukin-2021-0095](https://doi.org/10.2478/hukin-2021-0095)
- Efron, B. & Morris, C. (1975). Data Analysis Using Stein's Estimator. *JASA* 70(350), 311–319.
  [doi:10.1080/01621459.1975.10479864](https://doi.org/10.1080/01621459.1975.10479864)
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the False Discovery Rate. *JRSS-B* 57(1),
  289–300. [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)

## Open questions

**Sporting.** The one club still separating, at 1.177 across three managers and with no unusual
referee draw. Nobody was arguing about Sporting, which is part of why it is interesting.

**Absolute versus relative quality: tested, and still open.** Our strength measure is standardised
within league, so a Celtic–St Mirren fixture scores as "high quality" on the same scale as
Barcelona–Getafe. The gradient does vary a lot between leagues, from −0.040 in Spain to −0.110 in
Belgium, and that variation is real rather than noise: 91% of it survives correcting for how
precisely each league's gradient is estimated.

Absolute quality looked like the explanation and is not. Against UEFA association coefficients the
gradient correlates at +0.61, but the association does not survive controlling for home advantage
(+0.50, p = 0.14). Home advantage itself correlates at +0.79 across the eleven leagues, which is
stronger, stable under leave-one-out, and survives correcting for having tried seven league-level
covariates.

It is also an artifact of aggregation.

![Two levels of aggregation](figures/fig7-aggregation-levels.png)

Splitting the same data into three-season blocks and asking whether a league's own gradient moves
when its own home advantage moves gives **−0.086, p = 0.50**, with the slope running the other way
in five of the six leagues that have enough blocks to fit one. The test can detect a correlation of
0.35 at 80% power, so it is not simply underpowered against a claimed 0.79.

| Unit | n | correlation |
|---|---|---|
| League averages | 11 | **+0.782** |
| Three-season blocks, pooled | 62 | +0.238 |
| Three-season blocks, within league | 62 | **−0.086** |

Produced by `scripts/aggregation_levels.py`, with each league's own slope in
[`aggregation.json`](aggregation.json).

Home advantage fell across the panel from 0.349 goals per match in 2001 to 0.220 in 2025, with the
crowd-free seasons visible as a trough. The gradient did not follow it.

So the question stays open, and the aggregation lesson is the same one as Wrong (3) above: a
correlation across eleven leagues is a correlation between eleven things that differ in many ways
at once. This is exploratory rather than pre-registered, and it is recorded here as a question not
answered rather than as a finding.

**What we cannot resolve at all.** Whether the same foul is punished more harshly in a bigger
match, or whether bigger matches simply contain more cardable fouls. Distinguishing those requires
foul-level video coding. That is the honest limit here.

## Reproduce this

```bash
uv run python scripts/build_discipline_story.py   # figures 1-7, and the club table
uv run python scripts/aggregation_levels.py       # figure 8, the aggregation test
uv run python scripts/strength_effect.py          # the cross-league association
uv run python scripts/portugal_referee_table.py  # the club table above
uv run python scripts/referee_decomposition.py
uv run python scripts/manager_travel.py
```
