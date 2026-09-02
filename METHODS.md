# Methods

The standing methodological contract. Written before the analysis, and binding on it.

This project exists because it is easy to produce a confident football statistic that is
worthless. The defences below are structural rather than aspirational: most are enforced by
tests, and the ones that are not are stated so a reader can hold the work to them.

## 1. The tri-anchor rule

No claim is published unless three things are present and named in the report:

| Leg | Requirement |
|---|---|
| **Data** | Derived from a committed, re-fetchable snapshot in `data/snapshots/` |
| **Football literature** | A real, resolvable citation for the *phenomenon* |
| **Data-science literature** | A real, resolvable citation for the *method* |

A finding with two legs is a **watchlist candidate**, not a publication.

## 2. Metric provenance

Every metric carries one of three tags, rendered visibly wherever the metric appears:

- **`LITERATURE`** — defined or used in peer-reviewed work, cited.
- **`INDUSTRY`** — an established analytics convention (PPDA, TSR). Sourced, but explicitly
  *not* peer-reviewed.
- **`COINED`** — ours. Labelled as ours, every time, with the reasoning and the caveats.

A coined metric is never described as established. This rule exists because the transcript that
seeded this project presented an invented metric as though it came from the literature.

## 3. Uncertainty before ranking

Raw per-match ratios on small samples are noise. Therefore:

- Team estimates are **partially pooled** toward the league mean (empirical Bayes / hierarchical
  model). Rankings use the shrunken posterior, never the raw value.
- Every point estimate is published with an interval.
- Below a metric's reliability threshold, no team is ranked at all.

The shrinkage weight `B = (α+β)/(α+β+n) → 1` as `n → 0`, so an early-season estimate collapses
to the league mean on its own. That self-silencing property is the primary defence, and it is free.

**Known implementation trap.** The method-of-moments prior must subtract sampling variance:
`s2_true = max(s2_obs − s2_samp, ε)`. Omitting `s2_samp` overestimates between-team variance,
weakens shrinkage, and manufactures exactly the outliers this pipeline exists to suppress. This
has a dedicated regression test against synthetic data with known `τ`.

## 4. Stabilisation

For a beta-binomial, reliability is `r(n) = n/(n + n₀)` where `n₀ = α+β` — so **the stabilisation
point is the prior sample size**, obtained free from the model already fitted.

There is peer-reviewed football-specific stabilisation work, and this project spent a fortnight
believing there was not. The claim came from not having found it rather than from having looked
properly, which is exactly the error the rest of this document exists to prevent.

The question has been asked. O'Donoghue and Ponting, *Equations for the Number of Matches Required
for Stable Performance Profiles* (2005), is literally it. Johnson, Murphy and Bower (2010),
[doi:10.1016/j.jsams.2009.10.244](https://doi.org/10.1016/j.jsams.2009.10.244), do it for A-League
football. Both are barely cited, and both pre-date event data entirely — but they exist, and any
reviewer in this field will know them.

What is defensible is the **method**, not the question: split-half reliability with empirical-Bayes
shrinkage, applied to modern rate metrics and to referee-level decision rates. Those searches do
come back empty. We compute our own table by randomised split-half correlation, stratified on
home/away and opponent strength (an odd/even split confounds reliability with the fixture
calendar), cross-checked against the model-based variance decomposition. Disagreement beyond 25%
indicates misspecification and fails a test.

The general rule this cost us: **absence of evidence in your own search is not evidence of absence
in the literature.** A novelty claim needs a positive search that found the neighbours, not a
negative one that found nothing.

## 5. Multiple comparisons

Scanning many teams across many metrics weekly manufactures findings by chance. Controls:

- Partial pooling handles teams-within-metric.
- The metric set is **pre-registered and frozen**; adding one after seeing a week's data is a
  pipeline failure. **No test enforces this yet.**
- **One publication per week maximum**, selected by a pre-registered priority order.
- Bayesian FDR `E[FD] = Σ(1−S)` logged every week, published set capped at 0.10.
- A **shadow Benjamini–Hochberg screen** is published alongside any club that is named. It is
  computed per study rather than logged centrally; where it disagrees with the pooled result, the
  disagreement is the story.

## 6. Claim levels

Language is bound to evidence. **The lint that would enforce this does not exist yet** — the
banned phrases below are a standard the author holds to, not a check the build runs. Written down
because a stated standard is auditable by a reader and a private intention is not.

The obstacle is scope rather than effort: all three studies use "because" methodologically, as in
"possible because both teams in a match face the same referee", so a token ban would be mostly
false positives. A workable version lints only the block between the title and the first section
heading, and only sentences naming a club or the metric.

| Level | Meaning | Permitted | Forbidden |
|---|---|---|---|
| **L0** | Nothing cleared the bar | "No outlier this week; the closest call failed *X*" | any assertion |
| **L1** | Descriptive; mechanism unknown | "*X* has the most extreme adjusted *Y*. We don't know why." | "because", "deliberately", "strategy" |
| **L2** | Hypothesis + pre-registered prediction | "One explanation is *Z*. If so, we expect… resolved on [date]." | causal verbs, "shows that" |
| **L3** | Confirmed pattern | "*X* is systematically doing *Y*, persisted *n* matches, survives adjustment" | "peer-reviewed"/"studies show" without a populated citation field |

## 7. Interpretability

A statistical outlier is only publishable if a tactical reading is plausible. Candidates are
tested cheapest-first, and each stage can reject: **data artifact → fixture artifact → byproduct
of another trait → deliberate strategy**. Failing to reject the first three is *not* evidence for
the fourth; positive evidence is required, and an L3 claim additionally requires human external
corroboration with a resolvable URL.

## 8. What we will not claim

- No causal language from observational team aggregates.
- No "best/worst team" framing.
- No single-week narrative from a single-week movement.
- No pooling of discipline ratios across leagues. Phatak et al. (2021) document Simpson's paradox
  on precisely this ratio: the pooled trend differs in direction from the within-league trends.

## 9. Pre-registration

The week's question and analysis choices are written into the report file **before** the data is
pulled. This prevents fishing, and it means any paper drawn from this work has a genuine
pre-registration trail rather than a reconstructed one.

## 10. Null results, and why there is no cadence promise

The format must be able to return nothing, and does so by design. The expected null rate is
pre-registered so a quiet period reads as the method working rather than the author failing. A
running counter is **planned and not yet published**.

**Publication is gated on evidence, not on the calendar.** No weekly commitment is made, because a
schedule and a standard eventually conflict, and the schedule wins — quietly, by lowering the bar
on a slow week. Every safeguard in this document exists to stop exactly that, so promising a
frequency would undermine all of them at once.

A format that can only ever say "look at this" is indistinguishable from the thing this repo was
built to correct.

## 11. Pressure-testing: try to kill your own finding first

A result is not ready because it is significant. It is ready when a genuine attempt to destroy it
has failed. Before publication, every finding is attacked on the six fronts below, and each
attempt is reported in the study whether or not it succeeded. A study carries a table naming every
attack with a status of run, skipped or not-applicable, so an attack that was never tried cannot
pass as one that was tried and survived.

**Specification.** What does the model assume that the data might not support? Assumptions that
look like arithmetic are the dangerous ones — this project shipped an expectation of
`cards = rate x fouls`, a proportional model through the origin, and only later measured that the
intercept is 13% to 47% of mean cards depending on the league. Cards per foul falls monotonically
from 0.195 at six fouls to 0.127 at eighteen. Because dominant clubs foul *less*, that
misspecification mechanically inflated precisely the clubs the finding was about.

**Aggregation.** At what level does the effect actually live? A club-level average will happily
attribute a match-level regularity to one of the two participants. The test is cheap: compute the
same index for the *opponents*. If they move with it, the effect is not the club's.

**Adjustment coarseness.** Does a coarse control leave a gradient inside its own bins? Five
strength bands under-corrected the strongest clubs, so the analysis was redone with a continuous
fit. That one survived; the point is that it had to be tried.

**Prior work.** Has someone already found this? A gradient in cards by team strength was published
by Dawson, Dobson, Goddard and Wilson in 2007. Rediscovering a known result on more data is a
contribution; presenting it as new is not.

**Baseline sufficiency — what does a model with no team property already predict?**
Before asking whether a pattern reflects something about a team, compute what it would look like
if teams differed only in the means already known. Twice this has been the attack that killed a
finding, and in both cases the earlier four attacks had all been passed.

A second-half "swing" — a team's second-half goal difference minus its first-half — correlated with
strength at r = +0.22, in the same direction in all eleven leagues. It is an identity. About 55.9%
of goals are scored after half-time, a constant across every league (0.549-0.562) and 26 seasons.
If a team's goals for and against both split at that constant `s`, then
`swing = s(GF-GA) - (1-s)(GF-GA) = (2s-1)(GF-GA)`, so the swing is season goal difference rescaled
by 0.118 and carries no team property at all. Subtracting exactly what the identity predicts leaves
r = -0.04. The observed slope, 0.095, sits slightly *below* the arithmetic 0.118.

Draw rate is genuinely non-monotone in strength — an inverted U, quadratic term negative in 11/11
leagues. A Skellam distribution built only from each team's season goal means reproduces the same
curve. Excess over that baseline: r = -0.048. Blowout rate, clean-sheet rate, failure-to-score rate
and within-one-goal rate are all likewise fully accounted for by the means.

The generalisation worth carrying: **any "share of X in period P" metric is algebraically exposed
whenever the period split is near-constant across teams**, and any distributional-shape metric is
exposed to the moments it is built from. Report the excess over the matched null, never the raw
correlation. A cheap standing screen — resplit each team's totals under the league constant, or
simulate from the fitted means, and compare — catches both.

Note which attack *failed* here. Stratifying the swing by half-time score state inflated r from
+0.22 to +0.82, which reads as strong confirmation; the mechanical null reproduces the
within-stratum values to two decimals. A control that conditions on a post-treatment outcome can
manufacture the appearance of an effect, so a stratified result needs its own null.

**Cross-sectional associations across few units.** A correlation computed across a handful of
aggregate units is a correlation between things that differ in many ways at once, and it will
often not survive being asked at a finer grain. Test it within units before believing it.

The worked example cost nothing to find and would have cost a great deal to publish. Booking
gradients differ genuinely between the eleven leagues, and across those eleven league averages the
gradient correlates with home advantage at +0.78. It has every mark of a result: a plausible
mechanism, stability under leave-one-out, and survival of a Bonferroni correction for the seven
covariates tried. Splitting the same data into three-season blocks and asking whether a league's
own gradient moves when its own home advantage moves gives -0.09, sloping the other way in five
of the six leagues with enough blocks to fit a line, against a test able to detect 0.35 at 80%
power. Pooled at block level it is +0.24. One dataset, three levels of aggregation, and the
association is manufactured by the coarsest one.

The prompt that exposed it is worth recording too, because it was not a statistical objection: the
covariate varies from year to year, so why was it being used as a fixed league property? Asking
whether something moves over time is often the cheapest route to asking whether the effect is real.

**Independent replication is the strongest form of this.** Where a finding matters, it is re-derived
by a separate pipeline on a different subsample before publication. Twice in this project that
process reversed the conclusion — and a reversal found before publishing is a success of the
method, not a failure of it.

## 12. Corrections

**A report presents the current analysis, and the repository holds every version it has had.**

Corrections are not silent, and they are not footnotes either. This repository is public, every
change is a commit, and each commit message states what the number was, what it became, and how the
error was found. That record is complete, permanent and far more informative than an inline note,
and it is the reason a report does not need to carry its own changelog.

What a report must not do is accumulate. A page that reads as a sequence of revisions asks the
reader to reconstruct the argument from its own history, and the version they are shown should be
the one that survived. So a corrected figure is simply the figure, and `git log -p` on the file is
the erratum.

Two things this does not license. A conclusion that reversed is stated as a reversal in the report
itself, because that is part of the analysis rather than a change to it: study 02 is built around
three of them and says so in its title. And a retraction is published as a retraction, prominently,
never absorbed into a rewrite.

Retracting a finding in public remains a credibility asset. Presenting a finding as though it had
never been wrong, when the wrongness is itself the lesson, is not.
