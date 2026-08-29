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

There is **no peer-reviewed football-specific stabilisation table**. We compute our own by
randomised split-half correlation, stratified on home/away and opponent strength (an odd/even
split confounds reliability with the fixture calendar), cross-checked against the model-based
variance decomposition. Disagreement beyond 25% indicates misspecification and fails a test.

## 5. Multiple comparisons

Scanning many teams across many metrics weekly manufactures findings by chance. Controls:

- Partial pooling handles teams-within-metric.
- The metric set is **pre-registered and frozen**; adding one after seeing a week's data is a
  pipeline failure with a test to catch it.
- **One publication per week maximum**, selected by a pre-registered priority order.
- Bayesian FDR `E[FD] = Σ(1−S)` logged every week, published set capped at 0.10.
- A **shadow Benjamini–Hochberg screen** is computed and published alongside. Where it disagrees
  with the pooled result, the disagreement is the story.

## 6. Claim levels

Language is bound to evidence, and the binding is linted.

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

## 10. Null results

The weekly format must be able to return nothing, and does so by design. The expected null rate is
pre-registered so a quiet week reads as the method working rather than the author failing. A
running counter is published.

A format that can only ever say "look at this" is indistinguishable from the thing this repo was
built to correct.

## 11. Corrections

Errata are published, never silently edited. Reports are versioned; the tracker is append-only and
git-diffable; a correction appends a row and marks the superseded one. Retracting a finding in
public is treated as a credibility asset.
