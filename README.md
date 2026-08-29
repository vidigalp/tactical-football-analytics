# tactical-football-analytics

**LOVE your DATA / Learn with data**

Learning football tactics through statistics — reproducibly, with citations, and honest about
uncertainty. One finding a week, or an explicit *nothing this week*.

Every published claim rests on three anchors: **our own committed data**, **football literature**,
and **data-science literature**. A claim missing any one of them is a watchlist candidate, not a
publication, and the report builder enforces that.

## Why this exists

This project started from an AI-generated analysis of Portuguese league discipline. It contained
an invented league table, a metric the model had coined but presented as established literature,
and a discussion forum offered as a citation. Its headline statistic — a team at 31 fouls per card
— came from a single card in four matches.

The interesting question is not whether models hallucinate. It is **what verification layer makes
their output safe to act on**. This repo is one worked answer, applied to a subject where the
errors are checkable.

## What's here

| | |
|---|---|
| [`METHODS.md`](METHODS.md) | The methodological contract: shrinkage, multiplicity, claim levels, what we will not claim |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | Provenance, licensing boundaries, and what we measured versus what is documented |
| [`EDITORIAL.md`](EDITORIAL.md) | Neutrality policy. Football is tribal; this project is about measurement |
| [`AI_WORKFLOW.md`](AI_WORKFLOW.md) | Where AI is used, and where it is structurally distrusted |
| [`reports/`](reports/) | Weekly findings, each reproducible from a committed snapshot |
| [`references/`](references/) | Bibliography. Every DOI is resolved in CI; unverified entries are quarantined |

## Latest

**[Week 1 — What free football data can still tell you](reports/2026-W35/report.md)**

FBref lost its Opta licence in January 2026. I audited what remains: 286 league-season files
across 11 European leagues and 26 seasons. **179 carry fouls and cards.** The other 107 download
fine, parse fine, and contain no football. Median columns per file went from 25 to 131 since 2000
while the columns describing the match went from 0 to 12 and stopped moving in 2007.

## Reproduce it

```bash
uv sync --all-extras --dev
uv run python scripts/build_week01.py   # offline, from the committed snapshot
uv run pytest                           # includes live DOI resolution
```

## What free football data cannot do (2026)

Published here as a standing guard, because the documentation still implies otherwise.
**Unavailable from free sources for current seasons:** possession %, pass completion, pressures,
tackles, interceptions, progressive passes or carries, aerial duels, touches by zone, player-level
fouls or cards, foul location, foul timing, offsides, woodwork, free kicks conceded, and any
event-level data.

**Referee identity** is available in England and Scotland only.

## Licence

Code MIT. Text, figures and derived data CC BY 4.0. Match data courtesy of
[football-data.co.uk](https://www.football-data.co.uk/); this project is independent of, and not
endorsed by, any data provider, league or club.
