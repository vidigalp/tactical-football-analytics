"""A published report must not reference a figure that is not there.

Two figure bugs shipped before this existed. build_discipline_story.py derived
its output directory from the snapshot name rather than the report's, so week 2's
figures were written into week 1's folder; and build_week01.py raised on a
renamed frame, so week 1's figures stopped regenerating entirely. Neither failed
loudly, because a missing image renders as a broken icon rather than an error.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

#: ``![alt](figures/name.png)`` as written in a report.
FIGURE = re.compile(r"!\[[^\]]*\]\((figures/[^)]+)\)")


def reports() -> list[Path]:
    return sorted(REPORTS.glob("*/report.md"))


def references() -> list[tuple[Path, str]]:
    return [(r, m) for r in reports() for m in FIGURE.findall(r.read_text())]


def test_there_are_reports() -> None:
    """Guard the guards: an empty glob would make every test below vacuous."""
    assert reports(), "no reports found — the parametrised tests would pass on nothing"


@pytest.mark.parametrize("report,ref", references(), ids=lambda v: getattr(v, "name", v))
def test_referenced_figure_exists(report: Path, ref: str) -> None:
    assert (report.parent / ref).exists(), (
        f"{report.parent.name}/report.md references {ref}, which does not exist"
    )


@pytest.mark.parametrize("report,ref", references(), ids=lambda v: getattr(v, "name", v))
def test_referenced_figure_has_a_vector_sibling(report: Path, ref: str) -> None:
    """PNG for the web, PDF for print.

    Paper-grade means a reader can pull the figure into a document without it
    turning to mush, so the vector version is not optional.
    """
    pdf = (report.parent / ref).with_suffix(".pdf")
    assert pdf.exists(), f"{ref} has no vector sibling at {pdf.name}"


@pytest.mark.parametrize("report", reports(), ids=lambda p: p.parent.name)
def test_report_shows_at_least_one_figure(report: Path) -> None:
    """Images carry these arguments better than the prose does.

    Week 2 generated four figures and displayed one, including the chart that
    answered its own central question.
    """
    assert FIGURE.findall(report.read_text()), f"{report.parent.name} shows no figures"
