"""A published report must not reference a figure that is not there.

Two figure bugs shipped before this existed. build_discipline_story.py derived
its output directory from the snapshot name rather than the report's, so study 02's
figures were written into study 01's folder; and build_study01.py raised on a
renamed frame, so study 01's figures stopped regenerating entirely. Neither failed
loudly, because a missing image renders as a broken icon rather than an error.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

#: ``![alt](figures/name.png)`` as written in a report.
FIGURE = re.compile(r"!\[[^\]]*\]\((figures/[^)]+)\)")

#: A script named anywhere in a report or the README.
SCRIPT = re.compile(r"\b(scripts/[A-Za-z0-9_]+\.py)\b")

#: A JSON provenance sidecar a study links to as the source of its numbers.
#: Listed explicitly rather than matched as ``\w+\.json`` so that adding a
#: sidecar is a deliberate act; a study that links a file this does not know
#: about goes unchecked, which is the failure this test exists to prevent.
SIDECAR = re.compile(
    r"\]\((facts|persistence|numbers|chart|story|aggregation"
    r"|referee_table|season_status)\.json\)"
)


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


# ---------------------------------------------------------------------------
# Numeral provenance
#
# Four of the errors this repository has published shared one shape: a number
# reached a page with no committed script behind it. The 1.183 that should have
# been 1.179, a sign error, an understated tercile, a p-value nobody could
# reproduce. Every one was found by a human rereading prose.
# ---------------------------------------------------------------------------

#: Only numerals that carry a claim: a decimal, or thousands-grouped. A bare
#: small integer cannot be bound against a bag of values without matching one by
#: luck, and a check that passes numbers having no source is worse than none.
#: Every drift this catches was a decimal or a grouped thousand.
CLAIM_NUMERAL = re.compile(r"\d{1,3}(?:,\d{3})+|\d+\.\d+")

#: Spans of a report that carry numerals which are not claims about football.
#:
#: Order matters, and got this wrong once in a way worth recording. Stripping
#: ``](target)`` first leaves an image as a dangling ``![alt``, so an alt-text
#: pattern then runs on to the next ``]`` in the document — which, in study 02,
#: is the ``[1.094, 1.264]`` of a confidence interval eight lines later. That
#: silently unchecked the club table this whole test exists to guard. Images and
#: links are therefore consumed whole, and alt text may not cross a newline.
MASKS = (
    re.compile(r"```.*?```", re.S),          # fenced code
    re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)"),  # images, whole
    re.compile(r"\[[^\]\n]*\]\([^)\n]*\)"),   # links, whole
    re.compile(r"`[^`]*`"),                  # inline code, including filenames
    re.compile(r"CC BY(?:-SA)? \d+\.\d+"),   # licence versions
    re.compile(r"\b\d+\(\d+\)"),             # journal volume(issue)
    re.compile(r"\b\d+[-\u2013]\d+\b"),      # page ranges and season codes
    re.compile(r"\b(?:19|20)\d{2}\b"),       # years
    re.compile(r"\bstudy \d\d\b", re.I),
)

UNBOUND = tomllib.loads((REPORTS / "unbound.toml").read_text())


def _numeric(obj: object, out: list[float]) -> list[float]:
    if isinstance(obj, dict):
        for value in obj.values():
            _numeric(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _numeric(value, out)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, (int, float)):
        out.append(float(obj))
    return out


def sidecar_values(report: Path) -> list[float]:
    """Every number this report's own sidecars contain."""
    values: list[float] = []
    for path in sorted(report.parent.glob("*.json")):
        _numeric(json.loads(path.read_text()), values)
    return values


def claim_numerals(report: Path) -> list[str]:
    text = report.read_text()
    # The references and tri-anchor sections carry citation numerals only.
    text = re.split(r"^##+ *(?:References|Tri-anchor)", text, flags=re.M)[0]
    for mask in MASKS:
        text = mask.sub(" ", text)
    return sorted(set(CLAIM_NUMERAL.findall(text)))


def rounds_to(numeral: str, values: list[float]) -> bool:
    """Does any source value equal this numeral at the precision it is written?

    A report saying 0.051 is bound by a sidecar holding 0.05128, and one saying
    15% is bound by 0.1516. Matching at the displayed precision is what makes
    the check tight enough to catch 1.183 against 1.179 while still allowing a
    report to round.
    """
    raw = numeral.replace(",", "")
    target = float(raw)
    places = len(raw.split(".")[1]) if "." in raw else 0
    # Compared on magnitude: the regex cannot include a leading minus without
    # also swallowing en-dashes in ranges, and a report writes "r = -0.076"
    # against a stored -0.0759. A sign flip is caught by reading, not here.
    return any(
        round(abs(value), places) == target
        or round(abs(value) * 100, places) == target
        for value in values
    )


def numeral_cases() -> list[tuple[Path, str]]:
    return [(r, n) for r in reports() for n in claim_numerals(r)]


@pytest.mark.parametrize(
    "report,numeral", numeral_cases(), ids=lambda v: getattr(v, "name", v)
)
def test_every_numeral_is_bound(report: Path, numeral: str) -> None:
    allowed = UNBOUND.get(report.parent.name, {})
    if numeral in allowed:
        assert allowed[numeral].strip(), (
            f"{report.parent.name} allow-lists {numeral} with an empty reason"
        )
        return
    assert rounds_to(numeral, sidecar_values(report)), (
        f"{report.parent.name} states {numeral}, which no sidecar in "
        f"{report.parent.name}/ supplies at that precision. Either write it from "
        f"the script that computes it, or add it to reports/unbound.toml with a "
        f"reason."
    )


def test_there_are_numerals_to_bind() -> None:
    """Guard the guards: a broken mask would vacate the test above."""
    assert len(numeral_cases()) >= 25


@pytest.mark.parametrize("report", reports(), ids=lambda p: p.parent.name)
def test_allowlist_stays_small(report: Path) -> None:
    """The allowlist is the friction dial, and it only works while it hurts.

    Two entries, both cross-study references. If this number climbs, the check
    is being evaded rather than satisfied.
    """
    assert len(UNBOUND.get(report.parent.name, {})) <= 2


def test_allowlist_names_real_reports_and_numerals() -> None:
    """An allowlist entry for a numeral no longer written is dead weight, and it
    hides the fact that the numeral stopped being unbindable."""
    names = {r.parent.name for r in reports()}
    for name, entries in UNBOUND.items():
        assert name in names, f"unbound.toml names {name}, which is not a report"
        report = REPORTS / name / "report.md"
        stated = claim_numerals(report)
        for numeral in entries:
            assert numeral in stated, (
                f"unbound.toml allow-lists {numeral} for {name}, which no longer "
                f"states it"
            )


# ---------------------------------------------------------------------------
# Script provenance
# ---------------------------------------------------------------------------

#: The sidecar a script declares it writes, e.g. ``REPORT / "story.json"``.
DECLARED_SIDECAR = re.compile(r'REPORT\s*/\s*"([a-z_]+\.json)"')

#: Scripts a report may name without producing a sidecar beside it, and why.
#: Both write their output into ``data/``, which is the artifact a reader
#: reproduces from; a report-local JSON would duplicate the manifest.
INGEST_ONLY = {
    "scripts/run_audit.py": "writes the snapshot and its manifest under data/snapshots/",
    "scripts/ingest_events.py": "writes the foul extract and its manifest under data/events/",
    "scripts/ingest_matches.py": "writes match parquets into the snapshot",
}


def report_script_cases() -> list[tuple[Path, str]]:
    """Scripts named inside a report, paired with that report."""
    return [
        (report, script)
        for report in reports()
        for script in dict.fromkeys(SCRIPT.findall(report.read_text()))
    ]


@pytest.mark.parametrize(
    "report,script", report_script_cases(), ids=lambda v: getattr(v, "name", v)
)
def test_named_script_writes_a_sidecar(report: Path, script: str) -> None:
    """A script a report tells you to run must leave its numbers behind.

    Fourteen of nineteen scripts printed to stdout and wrote nothing, so their
    numbers were transcribed from a terminal into prose and then diverged from
    the code without anything failing. This is the assertion that converts them.
    """
    if script in INGEST_ONLY:
        assert INGEST_ONLY[script].strip()
        return
    source = (ROOT / script).read_text()
    declared = DECLARED_SIDECAR.findall(source)
    assert declared, (
        f"{report.parent.name} tells the reader to run {script}, which writes no "
        f"sidecar. Either write its numbers to a JSON beside the report, or add "
        f"it to INGEST_ONLY with a reason."
    )
    for name in declared:
        assert (report.parent / name).exists(), (
            f"{script} declares it writes {name}, which is not committed in "
            f"{report.parent.name}/"
        )


def test_there_are_script_cases() -> None:
    """Guard the guards."""
    assert len(report_script_cases()) >= 10


# ---------------------------------------------------------------------------
# Pressure tests
# ---------------------------------------------------------------------------

#: The six attacks METHODS.md section 11 requires. Named here so that adding a
#: seventh to the contract fails every report until each one answers it.
ATTACKS = (
    "Specification",
    "Aggregation",
    "Adjustment coarseness",
    "Prior work",
    "Baseline sufficiency",
    "Cross-sectional, few units",
)

#: A status a report may declare for an attack. "skipped" is deliberately
#: available: the purpose of the table is that an attack nobody tried reads as
#: untried rather than as survived.
STATUSES = ("run", "skipped", "not applicable")


def pressure_section(report: Path) -> str:
    text = report.read_text()
    match = re.search(r"^## Pressure tests\n(.*?)^## ", text, re.S | re.M)
    return match.group(1) if match else ""


@pytest.mark.parametrize("report", reports(), ids=lambda p: p.parent.name)
def test_report_has_a_pressure_test_table(report: Path) -> None:
    """Section 11 lists six attacks. Applying four and staying quiet about the
    other two is indistinguishable, to a reader, from applying six.

    That was the live state: baseline sufficiency was absent from both findings,
    and section 11 says it is the attack that killed two earlier ones.
    """
    assert pressure_section(report), (
        f"{report.parent.name} has no '## Pressure tests' section"
    )


@pytest.mark.parametrize(
    "report,attack",
    [(r, a) for r in reports() for a in ATTACKS],
    ids=lambda v: getattr(v, "name", v),
)
def test_every_attack_has_a_status(report: Path, attack: str) -> None:
    section = pressure_section(report)
    row = next(
        (line for line in section.splitlines() if line.startswith(f"| {attack} ")),
        None,
    )
    assert row is not None, (
        f"{report.parent.name} names no row for the '{attack}' attack"
    )
    assert any(status in row for status in STATUSES), (
        f"{report.parent.name}'s '{attack}' row declares no status from {STATUSES}"
    )
    # A status with nothing after it is the silence this table exists to remove.
    # The bar is low on purpose: "Nothing is adjusted for." is the complete and
    # honest account for a report that fits no model, and demanding more would
    # buy padding rather than substance.
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert len(cells) >= 3, f"{report.parent.name}'s '{attack}' row is malformed"
    assert len(cells[2]) >= 20, (
        f"{report.parent.name}'s '{attack}' row gives no account of what happened"
    )


# ---------------------------------------------------------------------------
# Relative links
# ---------------------------------------------------------------------------

#: ``](../<slug>/report.md)`` — a link from one report to another.
CROSS_REPORT = re.compile(r"\]\(\.\./([^/)]+)/report\.md\)")

#: ``](../../FILE.md)`` — a link from a report up to a repository document.
REPO_DOC = re.compile(r"\]\(\.\./\.\./([^)]+)\)")


def cross_report_links() -> list[tuple[Path, str]]:
    return [(r, m) for r in reports() for m in CROSS_REPORT.findall(r.read_text())]


@pytest.mark.parametrize(
    "report,target", cross_report_links(), ids=lambda v: getattr(v, "name", v)
)
def test_cross_report_link_resolves(report: Path, target: str) -> None:
    """Splitting one report into three created these links, and a typo in one
    would be invisible until a reader clicked it."""
    assert (REPORTS / target / "report.md").exists(), (
        f"{report.parent.name} links ../{target}/report.md, which does not exist"
    )
    assert target != report.parent.name, (
        f"{report.parent.name} links to itself as though it were another report"
    )


@pytest.mark.parametrize(
    "report,target",
    [(r, m) for r in reports() for m in REPO_DOC.findall(r.read_text())],
    ids=lambda v: getattr(v, "name", v),
)
def test_repo_document_link_resolves(report: Path, target: str) -> None:
    assert (ROOT / target).exists(), (
        f"{report.parent.name} links ../../{target}, which does not exist"
    )


def test_there_are_cross_report_links() -> None:
    """Guard the guards. The split is the reason these exist at all."""
    assert len(cross_report_links()) >= 5
