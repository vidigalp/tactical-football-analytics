"""Citation integrity — the structural answer to how this project began."""

from __future__ import annotations

import pytest

from tfa.citations import (
    PROVENANCE_TIERS,
    UNVERIFIED_BIB,
    VERIFIED_BIB,
    CitationError,
    Reference,
    assert_not_cited,
    check_resolves,
    check_structure,
    load,
    parse_bibtex,
)


@pytest.fixture(scope="module")
def verified():
    return load(VERIFIED_BIB)


@pytest.fixture(scope="module")
def unverified():
    return load(UNVERIFIED_BIB)


def test_bibliography_is_not_empty(verified):
    assert len(verified) >= 20


def test_every_entry_is_structurally_valid(verified):
    problems = check_structure(verified)
    assert problems == [], "\n".join(problems)


def test_every_entry_declares_a_known_provenance_tier(verified):
    for key, ref in verified.items():
        assert ref.provenance in PROVENANCE_TIERS, key


def test_preprints_are_labelled_as_preprints(verified):
    # xB is a preprint. Citing it as peer-reviewed is exactly the error this
    # project exists to avoid.
    assert verified["azmat2024xb"].provenance == "preprint"


def test_every_entry_has_a_resolvable_target(verified):
    for key, ref in verified.items():
        assert ref.resolvable_url(), key


def test_parser_reads_fields():
    refs = parse_bibtex(
        """
        @article{demo2020,
          author = {Doe, Jane},
          title = {A Title},
          year = {2020},
          doi = {10.1000/demo},
          provenance = {peer-reviewed}
        }
        """
    )
    assert refs["demo2020"].fields["author"] == "Doe, Jane"
    assert refs["demo2020"].doi == "10.1000/demo"


def test_structure_check_catches_missing_provenance():
    refs = {"x": Reference("x", "article", {"title": "T", "year": "2020", "doi": "10.1/x"})}
    assert any("provenance" in p for p in check_structure(refs))


def test_structure_check_catches_unverifiable_entry():
    refs = {
        "x": Reference(
            "x", "article", {"title": "T", "year": "2020", "provenance": "peer-reviewed"}
        )
    }
    assert any("cannot be verified" in p for p in check_structure(refs))


def test_quarantine_is_disjoint_from_verified(verified, unverified):
    assert not set(verified) & set(unverified)


def test_quarantined_entries_record_why(unverified):
    for key, ref in unverified.items():
        assert "status" in ref.fields, f"{key}: quarantined without a reason"


def test_citing_quarantined_reference_fails(unverified):
    key = next(iter(unverified))
    with pytest.raises(CitationError):
        assert_not_cited([key], unverified)


def test_citing_verified_reference_passes(unverified):
    assert_not_cited(["phatak2021dirty"], unverified)  # must not raise


@pytest.mark.network
def test_every_verified_reference_resolves(verified):
    failures = []
    for key, ref in sorted(verified.items()):
        ok, detail = check_resolves(ref)
        if not ok:
            failures.append(f"{key}: {ref.resolvable_url()} -> {detail}")
    assert not failures, "unresolvable references:\n" + "\n".join(failures)
