# Learning log

What I learned each week, in my own words — one football concept, one method. Kept publicly
because the curve is the point: this is a record of learning a subject, not a performance of
already knowing it.

---

## Week 1 — 2026-08-29

### Football concept: referee identity is a first-order confounder

I had assumed a foul-to-card ratio mostly measures how a *team* behaves. The disciplinary
literature says otherwise. Dawson et al. (2007) find referee-to-referee inconsistency in card
issuance large enough that two teams behaving identically will show different card rates purely
from which officials they drew. Boyko et al. (2007) add a venue effect: away teams are booked more
per foul under crowd pressure.

So "this team gets away with more fouls" is, in a small sample, substantially a statement about
their fixture list's refereeing assignments.

The part I find genuinely elegant: **you can remove the referee without observing them.** Both
teams in a match face the same official, so comparing a team's share of that match's fouls
cancels referee strictness exactly — along with tempo, weather, and league norms. A constraint
in the data forced a better model than I would have chosen freely.

### Method: content negotiation is a better citation check than an HTTP request

I wired a CI job to verify every reference resolves. My first version fetched the DOI URL and
checked for a 200. Fifteen of twenty-five "failed" — all HTTP 403, because publishers block
automated clients from landing pages. The check was measuring bot-blocking, not citation validity.

The right tool is **DOI content negotiation**: request `application/vnd.citationstyles.csl+json`
from `doi.org` and you get the registered metadata back. That confirms the DOI exists *and* lets
you compare the registered title against the one you claimed.

That second comparison is the one that matters, and I learned why the hard way. It immediately
failed on a reference I had written myself — I'd recorded a DOI by construction rather than
lookup, and it pointed at a paper about circuit training in prepubertal boys.

**A fabricated identifier is easy to catch. A real identifier attached to the wrong work is not.**
That is the failure that survives review, and I produced one within an hour of writing the rule
against it.

### What surprised me

That the *audit* was more interesting than the analysis it was meant to enable. I set out to
measure fouls and found that 107 of 286 league-season files contain no football at all, while
downloading and parsing without a single warning.

---

## Week 2 — 2026-08-29

### Football concept: match situation moves discipline more than any club does

I went looking for a club effect and found a situational one that dwarfs it. Across the whole
Portuguese league, a team booked as a heavy underdog receives **1.12** yellows per yellow its foul
count predicts; a heavy favourite receives **0.85**. That is a 32% swing driven by nothing but the
situation a side is in.

The mechanism is readable once you see it. Favourites foul higher up the pitch, in front of the
ball, breaking up attacks that are a long way from their own goal. Underdogs foul while defending
deep, under pressure, in positions where the same challenge is a bookable one. Same action,
different geography, different sanction.

That reframes what "a team gets away with fouling" even means. Most of it is where the fouls
happen, and where the fouls happen is decided by how good you are relative to the opponent.

### Method: adjust before you conclude, and be willing to lose your finding

Porto's raw booking index was 0.884, comfortably separable from the league. Adjusted for era and
match context it is **1.014**, indistinguishable from average. The finding evaporated, and it
should have.

Two adjustments, both necessary:

1. **Era.** League fouls-per-yellow fell from about 8.8 to 6.0 over twenty-five years. A manager
   holding a seven-season tenure would otherwise appear to change his team when only the
   refereeing had moved. Sérgio Conceição's raw numbers run 8.15 down to 4.92 across his tenure —
   which looks like a collapse in discipline and is entirely the league moving underneath him.
2. **Context.** The 32% favourite effect above.

The lesson I keep relearning: an unadjusted comparison is not a weak version of an adjusted one.
It is frequently a different answer.

### Method: the null test that actually settles causation-ish questions

To ask whether the effect belongs to the manager, compare managers who moved. Sixteen of them held
spells at two or more clubs, giving 46 pairs. Each spell was measured against its club's baseline
**excluding that manager** — otherwise a long tenure defines the baseline it is being judged
against, and the effect vanishes by construction.

Correlation between a manager's own spells: **r = −0.06**, permutation p = 0.67. Spells land on the
same side of their club baseline 39% of the time; chance is 50%. Only 8% of spell-to-spell
variation is between managers rather than within them.

A manager's own spells disagree with each other as much as different managers do. That is what a
real null looks like, and it is far more informative than a weak positive would have been.

### What surprised me

Chasing a fabricated claim about Porto produced a genuine finding about **Sporting** — the one club
in twenty that still separates after adjustment, booked 18% more than expected, consistently, under
three different managers. Nobody appears to have written about it.

I also lost the original finding twice: once to shrinkage, once to context adjustment. Both times
the honest answer was smaller and more interesting than the one I started with.
