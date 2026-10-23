# tactical-football-analytics

**LOVE your DATA / Learn with data**

Learning football tactics through statistics — reproducibly, with citations, and honest about
uncertainty.

**This repository is the research: data, analysis, figures and prose.** It does not build a
website. The studies are published at [pedrovidigal.com](https://pedrovidigal.com), whose source
lives in [vidigalp/pedrovidigal.com](https://github.com/vidigalp/pedrovidigal.com) and which reads
this repository as a pinned submodule. That pin is deliberate: the site records the exact commit of
the research it published, so a page and the script behind its numbers can never drift apart.

Everything needed to reproduce a study is here and needs no part of the site:

```bash
uv sync --all-extras --dev
uv run pytest
uv run python scripts/build_study03.py    # figures and facts for study 03
```

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
| [`reports/`](reports/) | Findings, each reproducible from a committed snapshot |
| [`dashboard/`](dashboard/) | The season in progress, every league and club, regenerated weekly from the newest snapshot |
| [`references/`](references/) | Bibliography. Every DOI is resolved in CI; unverified entries are quarantined |

## Studies

**[How much of a booking index is real?](reports/04-how-much-of-an-index-is-real/report.md)**

Across 2,528 consecutive club-season pairs in 11 European leagues, 15.1% of single-season spread in
the adjusted booking index is a real club property (`r = +0.324`, positive in 11 of 11 leagues) and
84.9% is Poisson sampling noise. A club's own one-season raw ratio is beaten out of sample by 11.6%
simply by predicting the league mean, and by 13.3% via Empirical-Bayes shrinkage.

**[The lever nobody pulls](reports/03-the-lever-nobody-pulls/report.md)**

Whether a foul is punished depends enormously on where and when it happens: 31.4% carded in a
team's own defensive fifth against 8.9% in the attacking fifth, and 6.5% in the opening quarter of
an hour against 25.6% after ninety minutes (with a 3.3-point drop across half-time and 25.7% in
late close-score defensive/middle-third situations). Across 98 clubs in five leagues, nobody
exploits it: club mean foul positions span 48.2 to 58.0 on a hundred-point pitch, leaving 91.2% of
between-club variation unexplained even on the defensive-third tail share.

**[A club that fouls with impunity, and the four ways I was wrong about it](reports/02-fouling-with-impunity/report.md)**

Across 58,013 completed matches and 246 clubs in 11 European leagues, raw cards-per-foul ratios
make nearly every domestic champion appear leniently officiated (`r = −0.371`). Adjusting for
single-match win expectation removes the favourite discount (1.098× heavy underdog vs. 0.856× heavy
favourite) but overshoots for elite clubs (`r = +0.484`) because high-quality fixtures elevate
card-per-foul rates for both teams on the pitch (`r = +0.283`; 11/11 leagues rising across
opponent-strength terciles). Netting out both the affine non-foul conduct intercept (11.1%–38.8%
league-mean share; 13%–47% across league-seasons) and fixture quality (`I_fix`)
eliminates the strength gradient across all 246 clubs (`r = +0.095, p = 0.139`) and pulls Europe's
domestic champions onto parity (≈ 1.00), while leave-one-club-out referee decomposition across 80
clubs in England, Scotland, and Portugal shifts club indices by an RMS of just 0.0085.

**[What free football data can still tell you](reports/01-free-football-data/report.md)**

FBref lost its Opta licence in January 2026. Auditing 286 league-season files across 11 European
leagues and 26 seasons reveals severe longitudinal truncation (179 of 286 files carry fouls and
cards; 107 download and parse cleanly with zero match statistics), unrecorded rule differences in
second-yellow accounting, non-foul conduct cards in the yellow-card numerator, and missing referee
identifiers across 9 of 11 European leagues.

## Reproduce it

Everything runs offline from the committed snapshot. Only the test suite touches the network, to
confirm every citation still resolves to the paper it claims.

```bash
uv sync --all-extras --dev

uv run python scripts/build_study01.py           # study 01: the data audit
uv run python scripts/build_discipline_story.py  # study 02: figures and the club table
uv run python scripts/booking_persistence.py     # study 02: season-to-season persistence
uv run python scripts/build_study03.py           # study 03: figures, facts and chart series
uv run python scripts/season_dashboard.py        # dashboard: the season in progress, every league

uv run pytest                                    # includes live DOI resolution
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
