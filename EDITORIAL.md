# Editorial policy

Football is tribal. This project is not. The line it argues is about **measurement**, never about
clubs.

## Neutrality

- **Systems, not villains.** Refereeing variation is analysed as inter-rater reliability — a
  measurement property present in code review, medical diagnosis and content moderation alike. It
  is never framed as bias, conspiracy or incompetence, and individual referees are not named in a
  bias framing.
- **Method first, club second.** Where a finding could read as praise or attack of one club, the
  method leads and the club is an illustration: not "*X* are geniuses" but "here is the league-wide
  curve, and *X* happens to sit here."
- **No adjudication of controversies.** We do not rule on whether a decision was correct. We
  describe distributions.
- **No piling on.** Relegation-battle and crisis-club angles are run as structural analysis out of
  season, not as live commentary on a struggling team.
- **No betting content.** Odds data is used only to derive an opponent-strength control. Nothing
  here is betting advice.

## Tone

Written for people who may not follow football. Every post carries a transferable methodological
point, because that is the part worth someone's time regardless of whether they watch matches.

Confidence is proportional to evidence. Hedging is not weakness here — an unhedged claim on six
matches is simply wrong, and the claim-level ladder in `METHODS.md` binds the language to the
evidence.

## Limitations are stated up front

Readers who work with data will probe methodology immediately. Getting ahead of that is both
honest and more persuasive than being caught by it — particularly for a project whose entire
premise is provenance.

## Where questions come from: controversy as a hypothesis generator

Football arguments are a good source of research questions. They are current, people already care
about the answer, and a claim that has gone viral is almost by definition one nobody has checked
properly. This project's first real finding started that way — from a post implying a club was
being favoured by referees.

Used carelessly this is also the fastest route to becoming exactly the thing the project exists to
correct. So it is governed:

**Test the claim, never the claimant.** We analyse a proposition — "club X is booked unusually
leniently" — not a person, an account, or a fanbase. Original posts are not linked, quoted or
named. There is no upside in directing attention at someone, and doing so converts an analysis
into a fight.

**Pre-register before looking.** The question, the metric, the adjustments and the threshold are
written down before the data is pulled. A claim generated from a striking observation is already a
garden-of-forking-paths problem; committing in advance is the only thing that makes the test
meaningful rather than a second bite at the same noise.

**Publish whichever way it lands.** Committing to publish before knowing the answer is what
separates a test from a search for ammunition. A null is a result and gets the same treatment.

**Expect mostly nulls, and say so up front.** This is the sharp edge. Claims go viral *because*
they are extreme, and extreme observations are disproportionately noise — that is regression to
the mean, not cynicism. A claim selected for being surprising is selected against being
representative. Anyone mining controversies for questions should expect to spend most weeks
reporting that the striking thing was ordinary, which is precisely why this project treats a null
week as publishable.

**Answer narrowly and state the limits loudly.** Cards per foul is not "favouritism". It says
nothing about penalties, offsides, disallowed goals, added time, or whether any single decision
was correct. A narrow finding stretched into a broad claim is how a chart becomes a talking point,
and the limits belong in the post itself rather than in a reply to whoever points them out.

**Never frame it as a rebuttal.** The output is "here is what this measure shows, and here is
everything it cannot see." Not "X was wrong." If the analysis happens to support the original
claim, it gets published in the same tone.

The value here is real: a partisan question, answered neutrally and in public, is more useful than
a neutral question nobody was asking.

### Format: lead with the finding, not the claim

Restating a claim in order to deny it makes the claim more familiar, and familiarity is itself
persuasive. The Debunking Handbook 2020 — a consensus statement of 22 researchers — puts the
ordering plainly: state the fact first, then the claim with a warning that it is being examined,
then why it does not hold, then the fact again. Applied here, a post opens with what the data
shows and how certain it is. The claim that prompted the question appears afterwards, unnamed,
and only as context.

A negation alone also does not work. The continued-influence effect (Lewandowsky et al. 2012) is
that a corrected claim keeps shaping people's reasoning unless something replaces it. So the
output is never "that is wrong" — it is "here is what the measure actually shows, and here is the
mechanism that explains the pattern someone noticed." Leaving a gap where the explanation was
invites the original account back in.

What this policy does **not** license is timidity. The fear that correcting a claim entrenches it
is not well supported: Wood and Porter (2019), across 52 issues and roughly 10,100 subjects, found
corrections moved factual beliefs toward the evidence and did not find backfire. Findings are
stated plainly, with their uncertainty, and hedged only to the degree the evidence requires.

### Selection is the bias that matters

Neutrality on any single question does not add up to neutrality across a body of work. If the
claims chosen for examination skew toward one club, one country, one political direction or one
kind of target, the project reads as partisan no matter how even-handed each individual analysis
is. Good intentions do not fix this, and self-assessment will not detect it.

So selection will be logged rather than trusted. **The ledger does not exist yet**; what follows
describes what it must record. A public ledger records every claim taken up — what was
examined, why it was selected, the pre-registered threshold, and how it resolved — including the
ones abandoned before publication. The distribution of *what gets checked* is published alongside
the distribution of *how it resolved*. If that distribution turns out to be lopsided, that is a
finding about this project and is reported as one.

### Who is worth examining

Only claims that have genuinely travelled, and only from accounts speaking to a large audience or
from institutions. Private individuals are never a subject, regardless of what they posted or how
widely it spread. A viral claim is a proposition in public circulation; the person who typed it is
not the object of study, and directing an audience at them would be both unkind and useless.

There is no attempt to keep up with the volume of unsupported claims — that is not winnable, and
trying converts the project into a reactive feed. Claims are selected for whether the data can
genuinely settle them and whether the method generalises, not for how much attention they are
getting.

### "This cannot be settled by data" is a first-class answer

Many circulating claims are not testable: they are definitional, they rest on a counterfactual
nobody observed, or the measurement needed does not exist. Establishing that, and showing precisely
where the evidence runs out, is a real contribution and is published as one. It is often more
useful than a verdict, because the reason a question is unanswerable is usually the interesting
part.

### The scepticism points inward first

A project that examines other people's claims accumulates authority, and authority is precisely
what this method distrusts. The correction is not modesty as a pose; it is that our own verdicts
get the same treatment as the claims that prompted them, and get it *before* publication.

Every finding runs the pressure tests in `METHODS.md` §11 — specification, aggregation, adjustment
coarseness, prior work, and baseline sufficiency — and the attempt is reported whether or not it
succeeded. This is not hypothetical. The project's own headline claim about booking rates was
retracted after the effect turned out to live at match level rather than club level. A
second-half-performance finding that agreed in sign across all eleven leagues died to an
arithmetic identity that no amount of significance testing would have caught. Both were ours, both
were found before publication, and both are published as failures.

Two commitments follow. **A verdict is never asserted more strongly than the data carries it** — no
rhetorical confidence standing in for evidence, since that is the exact failure being examined in
someone else's post. And **suspension of judgment is a legitimate and frequently correct output.**
"The data does not settle this" is not a failed investigation; it is the honest answer to most
interesting questions, and a project that never reaches it is not looking hard enough.

The public accountability mechanism is calibration, not reputation. Stated confidence is to be
logged against realised outcomes and the curve published. **Neither the log nor the curve exists
yet** — with three studies there is nothing to calibrate against, and a curve drawn from three
points would be decoration. It is recorded here as the commitment it is. Being right often matters less than the
claimed certainty matching the hit rate — a project that says "probably" and is right 70% of the
time is working; one that is never wrong has simply stopped saying anything falsifiable.

### The point is the method, not the verdict

The lasting contribution is not a series of adjudications. It is showing the working — what would
settle this, what data exists, what the analysis found, what remains uncertain, and why the
original observation looked compelling even when it does not survive. A reader who finishes a post
able to run the same check themselves has gained more than one who has merely been told an answer.
That is also the only version of this worth a career: an archive of transferable method, rather
than an archive of corrections.

## Corrections

Published, never silently edited. Every correction is a commit in a public repository whose
message states what the number was, what it became, and how the error was found, which is the
record `METHODS.md` §12 describes. **An errata page rendering that history on the site is planned
and not yet built.** A
retraction is a credibility asset, not an embarrassment.

## Conflicts of interest

This is a personal learning project. It is independent of the author's employer, of any club, and
of any data provider. It is unfunded and carries no advertising.
