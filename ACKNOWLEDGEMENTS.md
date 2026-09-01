# Acknowledgements

This project is built almost entirely on data that other people collected, maintained and gave
away. None of the analysis here would exist without them, and several have been maintaining these
resources for decades with no obligation to anyone.

## football-data.co.uk

The backbone of this project. Match-level results, shots, fouls, corners and cards for eleven
European divisions, some series running back to 1993, published as plain CSV files with an open
`robots.txt` and no rate limit.

Almost every number in this repository traces back to those files. Twenty-five years of
consistently formatted, freely available football data is a genuinely unusual public good, and it
is the reason a project like this can be reproduced by anyone who clones the repo.

**Thank you.** <https://www.football-data.co.uk/>

## Wikipedia and its contributors

The manager-tenure dataset — 182 spells across 29 Portuguese clubs — came from Wikipedia: the
*Managerial changes* tables in each season article, the club manager lists, and individual manager
biographies. Every row carries an inline citation to a club communiqué or a Portuguese press
report, added by volunteers who had no particular reason to be that careful.

The CC BY-SA licence is what made this straightforward rather than a legal question, and it is
worth saying that the licence choice itself is part of the gift.

**Thank you.** <https://www.wikipedia.org/>

## zerozero.pt (ZOS, Lda.)

Portuguese match officials, which exist in no open dataset we could find. Ten seasons of Primeira
Liga referee appointments, cleanly structured and publicly indexed.

We record our position honestly: their `robots.txt` disallows a single unrelated endpoint and
publishes a referee sitemap, and there is no AI-training clause or bot restriction. But the site
asserts all rights reserved and refers to terms we were unable to locate, so **this data is
permissible to access but not openly licensed**. We harvest at one request per second, store only
the factual mapping of match to official, and would remove it immediately on request.

**Thank you.** <https://www.zerozero.pt/>

## The scientific literature

This project leans heavily on statisticians who solved these problems long before football
analytics existed. Charles Stein and Willard James on shrinkage; Bradley Efron and Carl Morris for
making it usable; Lawrence Brown for showing it works out of sample in sport; Yoav Benjamini and
Yosef Hochberg on multiple comparisons; Andrew Gelman and colleagues on partial pooling. On the
football side, Phatak, Rein and Memmert; Wright and Hirotsu; Dawson and colleagues on referee
consistency.

Full references, each with a resolvable DOI, are in [`references/references.bib`](references/references.bib).

## Open-source tooling

pandas, NumPy, SciPy, matplotlib, Arrow, `uv`, ruff and pytest — all maintained by people
who mostly are not paid for it.

## Sources we deliberately did not use

Recorded for completeness, and with no criticism intended. These are excellent resources whose
terms simply do not permit this use:

- **FBref / Sports Reference** — terms prohibit building a database from their content and
  prohibit use by language models.
- **Transfermarkt** — the most complete manager-tenure source in existence; clause 11.1 prohibits
  automated access and AI use.
- **Liga Portugal** — has referee data and a permissive `robots.txt`, but its terms prohibit
  reproduction and grant only personal, non-commercial viewing.
- **FPF** — reserves rights under Article 4 of the EU DSM Directive.

Their terms are their choice, and respecting them costs this project a little coverage and no
integrity at all.

---

## If you maintain one of these sources

If anything here misrepresents your terms, or you would prefer we did not use your data, please
open an issue on the repository and we will correct or remove it promptly. Attribution and
compliance matter more to this project than any particular finding.
