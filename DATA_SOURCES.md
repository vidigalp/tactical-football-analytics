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

## Manager tenures — hand-assembled, and why not from Transfermarkt

Manager identity does not exist in any of the sources above, so it has to be assembled by hand.
That makes it the least reliable data here and the most in need of explicit handling: every row
cites a resolvable URL, date precision is recorded as day/month/season, and coverage is measured
and published rather than assumed. See `src/tfa/managers.py`.

**Transfermarkt is not used.** It is the most complete manager-tenure source in existence, and it
was the obvious candidate. Its terms of use, clause 11.1, rule it out twice over:

> "The User is not permitted to access or copy the Digital Content using bots, spiders, screen
> scraping or other automated processes. The user is also prohibited from using the digital content
> for the training or development of artificial intelligence (AI), including language models,
> machine learning, neural networks..."

Automated retrieval is prohibited, and use of the content by a language model is prohibited
outright — which matters directly for a project that documents an AI-assisted workflow. These
terms are near-identical to the Sports Reference terms that put FBref off this project's critical
path, so using Transfermarkt anyway would contradict our own published policy. Convenience is not
a reason to hold a second source to a lower standard than the first.

**Used instead**, in order of preference:

1. **Wikipedia** (Portuguese and English) — CC BY-SA, explicitly reusable with attribution, and it
   carries dedicated club manager-history pages.
2. **zerozero.pt** — Portuguese football database; permissive `robots.txt` that disallows a single
   endpoint and publishes a coaches sitemap.
3. **Club official sites** and **Liga Portugal**.
4. **Reputable news reports** for a specific appointment or departure, which have the advantage of
   dating the event precisely.

Anything unverifiable is left out and reported as a gap. A missing row costs coverage; an invented
one costs the project its premise.

## Event data — open, licensed, and historical only

Foul location, foul timing and player-level cards were recorded here as unavailable. That was
right about *current* seasons and wrong as a blanket claim, and the correction matters because it
changes what the project can attempt.

### Pappalardo et al. (2019) — CC BY 4.0

The best-licensed football data this project has found, better than the primary source.

- **Licence: CC BY 4.0**, confirmed through the figshare API on the Events, Matches and Referees
  files individually rather than inferred from the collection page. Attribution is the only
  condition; building a database, redistributing derived data and commercial use are all permitted.
- **Coverage:** complete 2017-18 seasons of the Italian, English, Spanish, French and German first
  divisions, plus Euro 2016 and the 2018 World Cup.
- **Contents:** spatio-temporal events with pitch coordinates. Cards are tagged `1701` red, `1702`
  yellow and `1703` second yellow — the separate second-yellow tag resolves the counting problem
  study 01 documented, where English and Scottish totals fold the first yellow of a second-bookable
  offence into the red.
- **Referee identity is included**, which is the confounder we had to assemble from zerozero.pt for
  Portugal.
- Documented in a peer-reviewed data paper, [doi:10.1038/s41597-019-0247-7](https://doi.org/10.1038/s41597-019-0247-7),
  itself CC BY 4.0. Cited as `pappalardo2019events`.

**No Portugal**, and a single season, so it cannot answer club-level questions: 85% of the spread
in a one-season booking index is sampling noise. It can answer whether foul context drives card
probability at all, on roughly 48,000 fouls.

### StatsBomb Open Data — free, but read the coverage carefully

- **Terms:** the repository README states that anyone publishing research based on the data should
  state StatsBomb as the source. A `LICENSE.pdf` accompanies it and is **image-only with no
  extractable text**, so it has not been read here and no claim is made about what it contains.
  Anyone relying on this source should read it first.
- **Contents:** fouls carry `location`, `minute` and `second`, `player`, `position`, `card`, foul
  `type`, plus `play_pattern` and a `counterpress` flag. The last two bear directly on tactical
  fouling.
- **Coverage is narrower than the season counts imply.** Measured from the repository:

  | Competition | Seasons | Matches per season |
  |---|---|---|
  | La Liga | 18 | 48 — one club's fixtures, not a league |
  | Champions League | 18 | 1 — finals only |
  | Premier League | 2 | 209 |
  | Serie A | 2 | 190, all twenty clubs |
  | Ligue 1 | 3 | 145 |

  A full domestic season is about 380 matches. Serie A, the Premier League and Ligue 1 are the
  parts with broad team coverage; the La Liga series is built around a single player's career and
  is not a sample of a league.

Neither source covers Portugal, so the question that started this project stays out of reach.

## zerozero.pt is currently returning 403

**Checked 2026-09-01.** Every request returns HTTP 403: the homepage, the referee endpoints, and
`robots.txt` itself, under both this project's user agent and a browser one. This is site-wide
rather than a rate limit.

The committed referee data is unaffected and stays where it is: 2,737 rows through 2026-08-29,
harvested when access was permitted, joined on scorelines and validated. Study 02 rests on it and
remains reproducible.

What it costs going forward is the ability to extend that coverage. The pre-registered test in
`preregistrations/2026-08-30-porto-booking-index.md` specifies a secondary referee analysis over
matchweeks 4 to 10; unless access returns, that part cannot be run and the resolution will say so
rather than quietly dropping it.

There is a compliance point here that matters more than the access one. This project's position was
that zerozero's `robots.txt` permitted the endpoints we used. **That file is now unreadable, so the
claim can no longer be checked, and an assertion about someone's crawl policy that cannot be
verified is not one to keep making.** No further harvesting will be attempted until the terms can be
read again.

## Not available at all

Published in the README as a permanent guard, so no future contributor builds on a column that
does not exist: pressures, tackles, interceptions, possession %, pass completion, progressive
passes or carries, aerial duels, touches by zone, offsides, woodwork and free kicks conceded.

**Corrected.** This list previously also claimed player-level fouls and cards, foul location and
foul timing were unavailable outright. They are unavailable *from the sources this project ingests*
and for *current* seasons and for Portugal, which is not the same statement. The open event data
described above carries all three for the five largest leagues in 2017-18. The original wording was
a claim about the world made from a search of a handful of sources, which is the error recorded in
`METHODS.md` §4: absence of evidence in your own search is not evidence of absence.

## Attribution

Match data courtesy of [football-data.co.uk](https://www.football-data.co.uk/). This project is
independent of, and not endorsed by, any data provider, league or club.
