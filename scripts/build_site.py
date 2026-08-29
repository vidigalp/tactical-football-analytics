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

PAGES = {
    "METHODS.md": "methods.md",
    "EDITORIAL.md": "editorial.md",
    "DATA_SOURCES.md": "data-sources.md",
    "AI_WORKFLOW.md": "ai-workflow.md",
    "NOTES/learning-log.md": "learning-log.md",
}


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "weekly").mkdir(exist_ok=True)

    for source, target in PAGES.items():
        shutil.copyfile(ROOT / source, DOCS / target)

    for report in sorted((ROOT / "reports").glob("*/report.md")):
        week = report.parent.name
        figures = DOCS / "weekly" / week / "figures"
        if (report.parent / "figures").exists():
            shutil.copytree(report.parent / "figures", figures, dirs_exist_ok=True)
        text = report.read_text()
        text = re.sub(r"\(figures/", f"({week}/figures/", text)
        (DOCS / "weekly" / f"{week}.md").write_text(text)

    index = ROOT / "README.md"
    home = index.read_text()
    # Repo-relative links resolve differently once rendered as a site.
    home = home.replace("](METHODS.md)", "](methods.md)")
    home = home.replace("](DATA_SOURCES.md)", "](data-sources.md)")
    home = home.replace("](EDITORIAL.md)", "](editorial.md)")
    home = home.replace("](AI_WORKFLOW.md)", "](ai-workflow.md)")
    home = home.replace("](reports/2026-W35/report.md)", "](weekly/2026-W35.md)")
    home = home.replace(
        "](reports/)",
        "](weekly/2026-W35.md)",
    ).replace(
        "](references/)",
        "](https://github.com/vidigalp/tactical-football-analytics/tree/main/references)",
    )
    (DOCS / "index.md").write_text(home)

    print(f"site source assembled in {DOCS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
