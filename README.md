# tactical-football-analytics

**LOVE your DATA / Learn with data**

Learning football tactics through statistics — reproducibly, with citations, and honest about
uncertainty.

Findings are published when they survive their own tests, not on a schedule. Some weeks that means
a result; some weeks it means an explicit *nothing cleared the bar*, with the near-misses shown.
A cadence promise would eventually be met by lowering the bar, and the bar is the point.

Every published claim rests on three anchors: **our own committed data**, **football literature**,
and **data-science literature**. A claim missing any one of them is a watchlist candidate, not a
publication, and the report builder enforces that.

## Why this exists

It started with a viral post implying a club was being favoured by referees. Rather than argue, I
went to check — and found the question was harder and more interesting than either side of the
argument assumed.

The first attempt, using an AI assistant, produced an invented league table, a metric the model had
coined but presented as established literature, and a discussion forum offered as a citation. Its
headline statistic — a team at 31 fouls per card — came from a single card in four matches.

So there are two problems here, and the repo addresses both. Football arguments are a good source
of research questions: current, widely cared about, and usually unchecked. And the tooling now
available to answer them will confidently invent an answer if you let it.

The interesting question is not whether models hallucinate. It is **what verification layer makes
their output safe to act on** — and whether a partisan question can be answered neutrally enough
to be worth reading. See [`EDITORIAL.md`](EDITORIAL.md) for how claims from controversies are
handled.

## What's here

| | |
|---|---|
| [`METHODS.md`](METHODS.md) | The methodological contract: shrinkage, multiplicity, claim levels, what we will not claim |
| [`DATA_SOURCES.md`](DATA_SOURCES.md) | Provenance, licensing boundaries, and what we measured versus what is documented |
| [`EDITORIAL.md`](EDITORIAL.md) | Neutrality policy. Football is tribal; this project is about measurement |
| [`AI_WORKFLOW.md`](AI_WORKFLOW.md) | Where AI is used, and where it is structurally distrusted |
| [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) | The people and projects whose freely-given data makes this possible |
| [`reports/`](reports/) | Weekly findings, each reproducible from a committed snapshot |
| [`references/`](references/) | Bibliography. Every DOI is resolved in CI; unverified entries are quarantined |

## Latest

**[Week 2 — A club that fouls with impunity, and the three ways I was wrong about it](reports/2026-W36/report.md)**

A viral post implied a club was being favoured by referees. Checking it produced a striking
result — and then three attempts to destroy that result, two of which succeeded. The effect turned
out to belong to the *fixture*, not the club: cards per foul scale with match quality, for both
teams. Being a heavy favourite is worth a 32% swing in booking rate on its own.

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
tackles, interceptions, progressive passes or carries, aerial duels, touches by zone, offsides,
woodwork and free kicks conceded.

**Player-level fouls and cards, foul location and foul timing** are unavailable for current seasons
and for Portugal, but not unavailable outright: Pappalardo et al. (2019) publish them under CC BY
4.0 for the five largest leagues in 2017-18. See [`DATA_SOURCES.md`](DATA_SOURCES.md).

**Referee identity** is available in England and Scotland only.

## Standing on other people's work

This project is built on data other people collected, maintained and gave away for free —
[football-data.co.uk](https://www.football-data.co.uk/) for twenty-five years of match data,
Wikipedia's contributors for manager histories, [zerozero.pt](https://www.zerozero.pt/) for
Portuguese match officials, and the statisticians who solved these estimation problems decades
before football analytics existed.

Proper thanks, and an honest note on what each licence does and does not permit, is in
[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md).

## Licence

Code MIT. Text, figures and derived data CC BY 4.0. Match data courtesy of
[football-data.co.uk](https://www.football-data.co.uk/); this project is independent of, and not
endorsed by, any data provider, league or club.
