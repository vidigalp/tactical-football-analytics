"""A published report must not reference a figure that is not there.

Two figure bugs shipped before this existed. build_discipline_story.py derived
its output directory from the snapshot name rather than the report's, so study 02's
figures were written into study 01's folder; and build_study01.py raised on a
renamed frame, so study 01's figures stopped regenerating entirely. Neither failed
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

#: A script named anywhere in a report or the README.
SCRIPT = re.compile(r"\b(scripts/[A-Za-z0-9_]+\.py)\b")

#: A JSON provenance sidecar a study links to as the source of its numbers.
SIDECAR = re.compile(r"\]\((facts|persistence|numbers|chart)\.json\)")


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


def documents() -> list[Path]:
    """Every file that tells a reader how to reproduce something."""
    return [ROOT / "README.md", *reports()]


def script_references() -> list[tuple[Path, str]]:
    return [
        (doc, match)
        for doc in documents()
        for match in dict.fromkeys(SCRIPT.findall(doc.read_text()))
    ]


@pytest.mark.parametrize(
    "document,script", script_references(), ids=lambda v: getattr(v, "name", v)
)
def test_named_script_exists(document: Path, script: str) -> None:
    """A reproduce block naming a deleted script fails silently.

    The repository shipped a workflow that called ``scripts/build_site.py`` for
    days after that script was removed. It never ran, so nothing complained.
    Instructions rot the same way and are read by people rather than machines.
    """
    assert (ROOT / script).exists(), (
        f"{document.name} names {script}, which does not exist"
    )


def test_there_are_script_references() -> None:
    """Guard the guards: a broken regex would make the test above vacuous."""
    assert len(script_references()) >= 4


@pytest.mark.parametrize("report", reports(), ids=lambda p: p.parent.name)
def test_linked_sidecar_exists(report: Path) -> None:
    """A study pointing at its own provenance should point at a file."""
    for name in SIDECAR.findall(report.read_text()):
        path = report.parent / f"{name}.json"
        assert path.exists(), f"{report.parent.name} links {name}.json, which does not exist"


def figure_files() -> list[tuple[Path, Path]]:
    """Every file sitting in a report's figures directory."""
    return [
        (report, path)
        for report in reports()
        for path in sorted((report.parent / "figures").glob("*"))
        if path.is_file()
    ]


@pytest.mark.parametrize(
    "report,figure", figure_files(), ids=lambda v: getattr(v, "name", v)
)
def test_no_orphan_figures(report: Path, figure: Path) -> None:
    """The converse of the test above: a report's figures directory holds only
    figures that report displays.

    Twenty-two files accumulated here, and the cause was not carelessness. Three
    scripts named their output directory after the latest *snapshot* rather than
    after the report, and while report directories were themselves named by ISO
    week the two were indistinguishable, so the wrong path silently resolved to
    a real study's folder. Renaming reports to their slugs broke that
    coincidence; this test is what makes the breakage loud.

    Checked in both directions because the earlier test only catches a reference
    with no file. An unreferenced file is the more dangerous direction: it is
    invisible in the rendered page, it is committed, it ships to the site's
    asset collector, and a reader who finds it has no way to know it is stale.
    """
    stems = {
        Path(ref).stem for source, ref in references() if source == report
    }
    assert figure.stem in stems, (
        f"{report.parent.name}/figures/{figure.name} is displayed by no report. "
        f"Either reference it or write it to scratch/ — see build_phase.py."
    )


def test_there_are_figures() -> None:
    """Guard the guards: an empty figures glob would vacate the test above."""
    assert len(figure_files()) >= 8
