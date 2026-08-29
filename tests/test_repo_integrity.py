"""Repository-level guards.

These assert properties of the tree itself rather than of any function: the
licensing boundary, and that published output cites nothing unverified.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tfa.citations import UNVERIFIED_BIB, assert_not_cited, load

ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return out.stdout.splitlines()


def test_no_third_party_data_committed():
    """FBref and Understat data must never enter this repo.

    Sports Reference's terms forbid building a data store from their content.
    Understat's terms are unreviewed. Either way the boundary is the same, and
    it is enforced here rather than trusted to discipline.
    """
    banned = re.compile(r"(fbref|understat|soccerdata)", re.IGNORECASE)
    offenders = [f for f in tracked_files() if banned.search(f)]
    assert not offenders, (
        f"third-party-sourced artifacts committed: {offenders}. "
        "See DATA_SOURCES.md — these caches belong outside every git tree."
    )


def test_snapshots_are_committed():
    """Reports must be reproducible from the repo alone."""
    snapshots = [f for f in tracked_files() if f.startswith("data/snapshots/")]
    assert any(f.endswith("manifest.json") for f in snapshots)
    assert any(f.endswith(".parquet") for f in snapshots)


@pytest.mark.parametrize("report", sorted((ROOT / "reports").glob("*/report.md")))
def test_reports_cite_nothing_unverified(report):
    text = report.read_text()
    unverified = load(UNVERIFIED_BIB)
    # Match by DOI, since reports cite in prose rather than by bibtex key.
    cited = {
        key
        for key, ref in unverified.items()
        if ref.doi and ref.doi in text
    }
    assert_not_cited(sorted(cited), unverified)


@pytest.mark.parametrize("report", sorted((ROOT / "reports").glob("*/report.md")))
def test_reports_declare_a_claim_level(report):
    assert re.search(r"\*\*Claim level:\*\*\s*L[0-3]", report.read_text()), (
        f"{report.name} does not declare a claim level — see METHODS.md section 6"
    )


@pytest.mark.parametrize("report", sorted((ROOT / "reports").glob("*/report.md")))
def test_reports_do_not_overclaim(report):
    """False-authority phrases require a populated citation nearby.

    The direct structural answer to this project's origin: an LLM describing its
    own coined metric as though it came from peer-reviewed work.
    """
    text = report.read_text()
    for phrase in ("peer-reviewed", "studies show", "research proves", "well established"):
        if phrase in text.lower():
            assert "doi.org" in text, (
                f"{report.name} uses {phrase!r} without any resolvable citation"
            )
