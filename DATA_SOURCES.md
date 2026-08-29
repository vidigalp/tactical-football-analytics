# Data sources and provenance

Everything published here traces to a committed snapshot in `data/snapshots/`, each carrying a
manifest with the source URL, fetch timestamp, row count, column-schema hash and a SHA-256 of the
raw bytes. Reports render from those snapshots offline, so any past result can be reproduced
exactly, and a silent upstream revision shows up as a hash change.

## Primary — football-data.co.uk

Match-level results, shots, shots on target, corners, fouls, cards, and a large betting-odds
block for eleven European top divisions.

- `robots.txt` is fully open; no rate limit is imposed; files are plain CSV.
- We identify ourselves with a descriptive User-Agent and fetch politely.
- The site's published disclaimer covers gambling liability only. **We found no explicit
  data-reuse or redistribution clause.** We therefore claim no licence over the underlying data,
  attribute the source on every page that uses it, and commit only the fields this project
  analyses. If the operator objects, we will comply.

### What we measured, versus what is documented

`notes.txt` describes a file that no longer exists. Verified 2026-08-29 by auditing 363
competition-seasons:

**Match statistics were never backfilled.** They arrived league by league over seventeen years.
Only **177 of 286** league-seasons since 2000 carry fouls and cards.

| First usable season (fouls + cards) | Leagues |
|---|---|
| 2000-01 | England, Scotland |
| 2003-04 | Germany |
| 2005-06 | Italy, Spain |
| 2007-08 | France |
| 2017-18 | Netherlands, Portugal, Turkey |
| 2019-20 | Belgium, Greece |

**`Referee` coverage narrowed over time.** England is continuous 2000–2025. Scotland is continuous
except 2012-13. Germany carried it in 2000-01 only; Italy in 2005-06 only. Both lost it.

**Documented columns that were dropped years ago** — fossils, not documentation errors:

| Column | Last observed |
|---|---|
| `HO`/`AO` (offsides), `HHW`/`AHW` (woodwork), `HBP`/`ABP` (bookings points) | 2000-01 |
| `HFKC`/`AFKC` (free kicks conceded) | 2017-18 |

**The files grew while the football shrank.** Median column count: 61 (2018) → 105 (2019) → 131
(2025). Nearly all of that growth is betting odds.

### Known quirks that affect interpretation

- **Second yellows.** In England and Scotland, the first yellow of a second-bookable offence is
  folded into the red and excluded from the yellow count; other countries count both. There is no
  dedicated second-yellow column anywhere. This is a classic silent discrepancy when comparing
  sources.
- **`HY`/`AY` are *all* yellows** — dissent, time-wasting, celebration, bench cards — while the
  natural denominator for a card rate is fouls only. This is a systematic, team-varying bias and
  must be stated wherever a card rate appears.
- **Portugal** has no files for 1997-98 through 1999-2000.
- **Betting odds** are used, if at all, only to derive a pre-match opponent-strength index. This
  project publishes no betting content and offers no betting advice.

## Enrichment — Understat (Big-5 only)

xG, non-penalty xG, PPDA and deep completions for the five major leagues.

**Status: not yet integrated.** Its terms of service will be reviewed before any code depends on
it, and the finding recorded here either way. `soccerdata` removed its FotMob scraper in January
2026 specifically because scraping it breached that site's terms; that is a live governance
question, not a footnote.

## Cross-check only — FBref / Sports Reference

**Not used as a data source, and never committed.**

- FBref **lost its Opta licence on 20 January 2026**. xG, possession, passing, progressive actions
  and defensive actions were removed site-wide, including historical archives. Pressures had
  already gone in the October 2022 provider switch. What remains is basic.
- Sports Reference's terms prohibit using site content "to create any database, archive, or other
  data store" that substitutes for their service, and separately prohibit use "for purposes of
  training, fine-tuning, prompting, or instructing artificial intelligence models."
- They enforce a limit of ten requests per minute by IP.
- The site is behind an interactive Cloudflare challenge, and cloud IP ranges are reported blocked,
  so it cannot run in CI regardless.

We respect all of that. If FBref is ever consulted locally for a goals/cards agreement check, the
result is reported as a summary statistic and the underlying data is never committed. A CI test
asserts no FBref-derived artifact exists in the tree.

## Not available at all

Published in the README as a permanent guard, so no future contributor builds on a column that
does not exist: pressures, tackles, interceptions, possession %, pass completion, progressive
passes or carries, aerial duels, touches by zone, player-level fouls or cards, foul location, foul
timing, offsides, woodwork, free kicks conceded, and any event-level data for current seasons.

## Attribution

Match data courtesy of [football-data.co.uk](https://www.football-data.co.uk/). This project is
independent of, and not endorsed by, any data provider, league or club.
