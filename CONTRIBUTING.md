# How this project is structured

This repository is one **study**. The initiative is method-first: a shared toolkit, and a series of
studies that apply it to different subjects and data sources.

```
evidence/                        the method, as code — no domain knowledge
  snapshot     versioned data with content hashes; offline re-derivation
  citations    DOI content negotiation with title matching, enforced in CI
  shrinkage    empirical Bayes, so small samples cannot shout
  theme        figures that will not save without their provenance

tactical-football-analytics/     study 1 — European league football
<future study>/                  study 2 — a different sport, a different feed
```

One repository per data source, because provenance is per-source. Licence terms, rate limits,
schema drift and quirks all attach to a feed rather than to a question, and mixing two feeds in one
repository makes it much harder to state honestly where any given number came from.

## What is automated, and what is not

The weekly workflow refreshes data, re-runs the scan, rebuilds figures and **opens a draft pull
request**. It does not publish.

That boundary is deliberate. `METHODS.md` requires human external corroboration before a strong
claim and a human interpretability review before publication. A fully automated post would be the
same failure this project was built to correct, arriving faster and with a nicer chart.

Automation is for the parts where a machine is more reliable than a person: fetching, hashing,
re-running a scan identically, and noticing that a number moved. Judgement stays human.

## Adding a study

1. New repository, one data source.
2. Depend on `evidence`; do not copy it.
3. Write `DATA_SOURCES.md` before the first fetch — terms, licence, known gaps.
4. Write the study's question down before pulling the data.
5. Reuse `METHODS.md` and `EDITORIAL.md` as they stand. They are deliberately domain-free.
