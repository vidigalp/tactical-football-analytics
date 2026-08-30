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
#: Both files are generated from STUDY_SLUGS rather than written by hand, because
#: the first hand-written version silently did nothing. Cloudflare matched only
#: the broad trailing splats: ``/weekly/*`` and ``/*`` fired, while
#: ``/weekly/2026-W36/*`` and ``/studies/*/figures/*`` never did. Every archived
#: week-numbered URL therefore landed on the studies index instead of its own
#: study, and figures were served ``max-age=0`` instead of the intended year.
#: Explicit paths, no wildcard except the final catch-all, verified live.


def _server_rules() -> tuple[str, str]:
    """Return (redirects, headers) for the current set of studies."""
    redirects = []
    for week, slug in sorted(STUDY_SLUGS.items()):
        target = f"/studies/{slug}/"
        # Both forms: Cloudflare does not treat these as the same path.
        redirects.append(f"/weekly/{week}   {target}  301")
        redirects.append(f"/weekly/{week}/  {target}  301")
    redirects.append("/weekly/*  /studies/  301")

    headers = [
        "/*",
        "  X-Content-Type-Options: nosniff",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  X-Frame-Options: DENY",
        "  Permissions-Policy: geolocation=(), microphone=(), camera=()",
        "",
        "# Figures change only when a study is rebuilt, so they cache for a year.",
    ]
    for slug in sorted(STUDY_SLUGS.values()):
        headers += [f"/studies/{slug}/figures/*",
                    "  Cache-Control: public, max-age=31536000, immutable",
                    ""]
    return "\n".join(redirects) + "\n", "\n".join(headers) + "\n"


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
        for source_page, target_page in PAGES.items():
            text = text.replace(f"](../../{source_page})", f"](../{target_page})")
        (DOCS / "studies" / f"{slug}.md").write_text(text)

    index = ROOT / "README.md"
    home = index.read_text()
    # Repo-relative links resolve differently once rendered as a site.
    for source_page, target_page in PAGES.items():
        home = home.replace(f"]({source_page})", f"]({target_page})")
    for week, slug in STUDY_SLUGS.items():
        home = home.replace(f"](reports/{week}/report.md)", f"](studies/{slug}.md)")
    # Point at the newest study, not at a redirect stub: mkdocs-redirects
    # synthesises weekly/* at build time, so they are not source pages and
    # --strict rejects a link to one.
    newest = STUDY_SLUGS[max(STUDY_SLUGS)]
    home = home.replace(
        "](reports/)",
        f"](studies/{newest}.md)",
    ).replace(
        "](references/)",
        "](https://github.com/vidigalp/tactical-football-analytics/tree/main/references)",
    )
    (DOCS / "index.md").write_text(home)

    redirects, headers = _server_rules()
    (DOCS / "_redirects").write_text(redirects)
    (DOCS / "_headers").write_text(headers)

    print(f"site source assembled in {DOCS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
