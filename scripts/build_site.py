"""Assemble the mkdocs source tree from the canonical files.

The repo is the source of truth; the site is a rendering of it. Documents are
copied rather than duplicated so the two can never disagree.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

#: Report directory -> durable study slug. Numbered so a citation stays valid.
STUDY_SLUGS = {
    "2026-W35": "01-free-football-data",
    "2026-W36": "02-fouling-with-impunity",
}

PAGES = {
    "METHODS.md": "methods.md",
    "EDITORIAL.md": "editorial.md",
    "DATA_SOURCES.md": "data-sources.md",
    "AI_WORKFLOW.md": "ai-workflow.md",
    "NOTES/learning-log.md": "learning-log.md",
    "ACKNOWLEDGEMENTS.md": "acknowledgements.md",
}


#: Server-side rules, emitted into ``docs/`` so mkdocs copies them verbatim.
#:
#: ``_redirects`` keeps URLs that were published under the old week numbering
#: resolvable. ``mkdocs-redirects`` already writes an HTML meta-refresh at each
#: of those paths, and Cloudflare serves an existing static asset in preference
#: to a redirect rule, so today the meta-refresh is what fires; these are the
#: fallback if those stubs are ever pruned. A project whose premise is that
#: cited artifacts stay reachable does not get to break its own links.
REDIRECTS = """\
/weekly/2026-W35/*  /studies/01-free-football-data/  301
/weekly/2026-W36/*  /studies/02-fouling-with-impunity/  301
/weekly/*           /studies/  301
"""

#: Figures are rewritten only by a rebuild, so they cache for a year. Nothing
#: here is authenticated, so the header set is about not being framed or
#: sniffed rather than about protecting a session.
HEADERS = """\
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Permissions-Policy: geolocation=(), microphone=(), camera=()

/studies/*/figures/*
  Cache-Control: public, max-age=31536000, immutable
"""


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "studies").mkdir(exist_ok=True)

    # Only GitHub Pages reads this; Cloudflare takes the domain from its own
    # dashboard. Written anyway so the GitHub fallback stays one click away.
    (DOCS / "CNAME").write_text("pedrovidigal.com\n")

    for source, target in PAGES.items():
        text = (ROOT / source).read_text()
        # Repo-relative links to files outside docs/ have to point at GitHub
        # once rendered as a site, or mkdocs --strict rejects them.
        text = text.replace(
            "](references/references.bib)",
            "](https://github.com/vidigalp/tactical-football-analytics"
            "/blob/main/references/references.bib)",
        )
        (DOCS / target).write_text(text)

    # Studies are numbered, not dated. A number is a stable citable handle;
    # a week number tells a reader the work is stale and advertises a schedule.
    for report in sorted((ROOT / "reports").glob("*/report.md")):
        week = report.parent.name
        slug = STUDY_SLUGS.get(week)
        if slug is None:
            continue
        figures = DOCS / "studies" / slug / "figures"
        if (report.parent / "figures").exists():
            shutil.copytree(report.parent / "figures", figures, dirs_exist_ok=True)
        text = report.read_text()
        text = re.sub(r"\(figures/", f"({slug}/figures/", text)
        # Reports link to repo-root policy docs with ../../; inside the site
        # those pages sit one level up from weekly/.
        text = text.replace("](../../EDITORIAL.md)", "](../editorial.md)")
        text = text.replace("](../../METHODS.md)", "](../methods.md)")
        text = text.replace("](../../DATA_SOURCES.md)", "](../data-sources.md)")
        (DOCS / "studies" / f"{slug}.md").write_text(text)

    index = ROOT / "README.md"
    home = index.read_text()
    # Repo-relative links resolve differently once rendered as a site.
    home = home.replace("](METHODS.md)", "](methods.md)")
    home = home.replace("](DATA_SOURCES.md)", "](data-sources.md)")
    home = home.replace("](EDITORIAL.md)", "](editorial.md)")
    home = home.replace("](AI_WORKFLOW.md)", "](ai-workflow.md)")
    home = home.replace("](ACKNOWLEDGEMENTS.md)", "](acknowledgements.md)")
    for week, slug in STUDY_SLUGS.items():
        home = home.replace(f"](reports/{week}/report.md)", f"](studies/{slug}.md)")
    home = home.replace(
        "](reports/)",
        "](weekly/2026-W35.md)",
    ).replace(
        "](references/)",
        "](https://github.com/vidigalp/tactical-football-analytics/tree/main/references)",
    )
    (DOCS / "index.md").write_text(home)

    (DOCS / "_redirects").write_text(REDIRECTS)
    (DOCS / "_headers").write_text(HEADERS)

    print(f"site source assembled in {DOCS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
