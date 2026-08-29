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
