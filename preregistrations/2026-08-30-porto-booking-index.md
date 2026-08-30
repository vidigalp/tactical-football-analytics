# Pre-registration — Primeira Liga booking index, 2026-27

**Written 2026-08-30. Status: SEALED. The matchweek-4 data does not exist at time of writing;
football-data.co.uk's Portugal file ends 2026-08-24, and no referee data has been harvested.**

This document exists because the analysis that prompted it was already contaminated, and saying so
is cheaper than pretending otherwise.

## Why this is being pre-registered mid-stream

A claim circulating publicly compares a club's fouls to its yellow cards over the opening
matchweeks. The claim is not linked, quoted or attributed here, per `EDITORIAL.md`.

On 2026-08-30 an exploratory analysis of matchweeks 1-3 was run **before** any pre-registration.
That analysis is **post-hoc and cannot be published as a test.** Specifically, its historical
rarity check used a "at least 35 fouls and at most 1 yellow" threshold chosen after seeing the
numbers it was applied to. That is a forking path, and the resulting "0 of 162" figure is
descriptive only. It is recorded here so the contamination is on the record rather than
discovered later.

What follows is a genuine forward test on data that does not yet exist.

## Frozen model

Fitted on Primeira Liga 2017-18 to 2025-26, 2,754 matches, 5,508 team-match observations,
excluding 2026-27 entirely:

```
E[yellows] = 1.1259 + 0.095491 x fouls
```

Affine, not proportional. The intercept is 44% of mean yellows per team-match, and cards per foul
falls monotonically with foul count (0.252 at <=8 fouls, 0.149 at 18+), so a proportional model
through the origin systematically misprices exactly the teams this is about. These two
coefficients are **frozen as of this document** and may not be refitted for this test.

Booking index = observed yellows / expected yellows. 1.0 is as-expected.

## Established before the test (matchweeks 1-3, already observed)

| | fouls | yellows | expected | index |
|---|---|---|---|---|
| Porto | 39 | 1 | 7.10 | 0.141 |
| Their opponents | 19 | 4 | 5.19 | 0.770 |

Long run, 2017-18 to 2025-26, same model, 306 matches each: Benfica 0.844 [0.779, 0.912],
Porto 0.893 [0.828, 0.962], Sp Braga 0.908 [0.842, 0.979], Sporting 1.003 [0.932, 1.077].

## Primary test

**Porto's yellow-card count across matchweeks 4 to 10 inclusive** (the next seven league matches),
against an expectation of 17.92 yellows built from their historical 15.02 fouls per match.

Bands fixed now:

| Outcome | Yellows in MW4-10 | Reading |
|---|---|---|
| **`REAL`** | **<= 7** | The opening is not a fluctuation |
| **`AMBIGUOUS`** | **8 to 11** | Underpowered; no claim either way |
| **`NOISE`** | **>= 12** | Consistent with their own long-run 0.893 |

Discriminating power, computed now:

| If true state is | P(<=7) | P(8-11) | P(>=12) |
|---|---|---|---|
| Opening persists (lambda 2.5) | 0.9958 | 0.0042 | 0.0000 |
| Reverts to long-run 0.893 (lambda 16.0) | 0.0100 | 0.1170 | 0.8730 |
| League average 1.0 (lambda 17.92) | 0.0030 | 0.0538 | 0.9431 |

If fewer than seven matches are played by 2026-11-15, the test resolves on whatever has been
played and the reduced power is reported. Postponements do not license waiting for a better number.

## Look-elsewhere

Porto is being examined because a claim named them, which is selection, not evidence. Therefore
**the identical test runs for all eighteen clubs**, and Porto's rank among them is published
whatever it is. A club that looks extreme in a set of eighteen is the expected outcome, not a
finding. If another club is more extreme than Porto, that is reported with equal prominence.

## Referee analysis (secondary, confirmatory only)

Referee identity is the dominant confounder for cards and is absent from football-data.co.uk for
Portugal. Officials will be harvested from zerozero.pt for 2026-27 under the existing terms
recorded in `DATA_SOURCES.md` — one request per second, factual match-to-official mapping only.

Pre-specified: for each official, compute their historical booking index across all their Primeira
Liga matches, then recompute Porto's index with the official's own tendency as an offset. Stated
in advance: **if the officials appointed to Porto's matches are historically lenient in general,
the club-level effect shrinks and that is reported as the explanation.** This is registered before
the referee names are known.

## Claim ceiling

**L1 (descriptive) regardless of outcome.** Card counts cannot distinguish leniency from clean
play, and this measure says nothing about penalties, offsides, disallowed goals or added time. No
causal language, no "favouritism" framing, and no adjudication of any individual decision. A
`REAL` result licenses "this is not a fluctuation" and nothing more.

## What would falsify the whole approach

- The affine model failing on 2026-27 league-wide (checked by residuals across all clubs).
- The Rio Ave data point standing: they are recorded with **1 foul** in their match against Porto,
  against a season minimum of 7 elsewhere. This is flagged as a probable recording error. If it is
  genuine the model is fine; if it is an error the opponent comparison for that match is void, and
  either way the analysis is rerun without it as a sensitivity check.

## Resolution

Resolves 2026-11-15 or on completion of matchweek 10, whichever is earlier. Result published
whichever way it lands, per `EDITORIAL.md`.
