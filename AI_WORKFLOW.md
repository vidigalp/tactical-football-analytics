# How AI is used here — and where it is distrusted

This project was seeded by a large language model producing a confident, well-formatted league
table of **entirely invented numbers**, a metric it had coined presented as though it came from
peer-reviewed literature, and Reddit offered as a citation. Its headline example — a team at 31
fouls per card — came from a single card in four matches.

That is not an argument against using AI. It is an argument for using it with a verification
harness. Documenting that harness is part of the point of this repo.

## Where LLMs are used

- **Literature discovery.** Finding candidate papers, which are then verified independently.
- **Code drafting.** Reviewed, tested, and owned by a human.
- **Hypothesis generation.** Proposing what might be worth measuring.
- **Editing.** Tightening prose.

## Where LLMs are structurally distrusted

Any **number**, any **citation**, any **claim**.

- No statistic enters a report except from a committed snapshot. Report text is generated from
  typed templates bound to fields in the run artifact: **a numeral with no bound field fails the
  build.** It is mechanically impossible to publish a number that is not traceable to data.
- Every citation must resolve to a live DOI or URL, checked in CI. A reference that cannot be
  verified goes to `references/unverified.bib` and may not be cited.
- Provenance tiers are recorded per reference. A preprint is not cited as peer-reviewed; an
  industry convention is not cited as literature.
- Claim-level language is linted. "Peer-reviewed", "studies show" and "research proves" fail the
  build unless a citation field is populated.

## The recurring theme

Periodically this repo audits AI-generated football analysis against verified data and publishes
the hit rate — including the founding example that started it.

The interesting question for anyone deploying these systems is not whether models hallucinate.
It is **what verification layer makes their output safe to act on**. That is an engineering
problem, and this repo is one worked example of solving it.

## Disclosure

AI assistance is used in producing this work. The methodology, the verification harness, and every
published claim are the author's responsibility.
