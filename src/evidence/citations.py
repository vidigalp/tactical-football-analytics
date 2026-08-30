"""Citation integrity.

A minimal BibTeX reader plus the checks that make the tri-anchor rule mechanical
rather than aspirational:

* every entry declares a provenance tier, and nothing may be cited above it;
* every entry carries a resolvable DOI or URL, verified against the network in CI;
* entries that cannot be verified live in ``unverified.bib`` and may not be cited.

This module is the structural answer to how this project began: an LLM produced a
citation to a discussion forum for a metric it had invented. Here, a reference that
does not resolve fails the build.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests

#: Where a study keeps its bibliography. Overridable, because this package is
#: meant to be dropped into a study rather than to own one.
REFERENCES_DIR = Path(
    os.environ.get("EVIDENCE_REFERENCES_DIR", Path.cwd() / "references")
)
VERIFIED_BIB = REFERENCES_DIR / "references.bib"
UNVERIFIED_BIB = REFERENCES_DIR / "unverified.bib"

#: Evidence tiers, weakest first. A claim may never describe a source as stronger
#: than the tier recorded here.
PROVENANCE_TIERS: tuple[str, ...] = (
    "blog",
    "industry",
    "observatory",
    "book",
    "preprint",
    "peer-reviewed",
)

_ENTRY_START = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
_FIELD_START = re.compile(r"(\w+)\s*=\s*\{")


def _matching_brace(text: str, open_index: int) -> int:
    """Index of the brace matching the one at *open_index*.

    BibTeX values legitimately contain braces (``Daum{\\'e}``), so field values
    cannot be extracted with a non-greedy regex — they have to be balanced.
    """
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unbalanced brace at position {open_index}")


@dataclass(frozen=True)
class Reference:
    key: str
    entry_type: str
    fields: dict[str, str]

    @property
    def provenance(self) -> str | None:
        return self.fields.get("provenance")

    @property
    def doi(self) -> str | None:
        return self.fields.get("doi")

    @property
    def url(self) -> str | None:
        return self.fields.get("url")

    @property
    def is_open_access(self) -> bool:
        return self.fields.get("openaccess", "").lower() == "yes"

    def resolvable_url(self) -> str | None:
        """Preferred URL for verification: DOI first, then an explicit URL."""
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.url


def parse_bibtex(text: str) -> dict[str, Reference]:
    """Parse the small BibTeX subset this project uses.

    Deliberately not a general parser. It handles the shape we write, and anything
    it cannot read is a reason to fix the file rather than the parser.
    """
    out: dict[str, Reference] = {}

    for match in _ENTRY_START.finditer(text):
        entry_type, key = match.group(1).lower(), match.group(2).strip()

        # The entry's own opening brace, so the body is bounded correctly even
        # when a field value contains braces of its own.
        entry_open = text.index("{", match.start())
        entry_close = _matching_brace(text, entry_open)
        body = text[match.end() : entry_close]

        fields: dict[str, str] = {}
        pos = 0
        while (field := _FIELD_START.search(body, pos)) is not None:
            value_open = field.end() - 1
            value_close = _matching_brace(body, value_open)
            raw = body[value_open + 1 : value_close]
            fields[field.group(1).lower()] = " ".join(raw.split())
            pos = value_close + 1

        out[key] = Reference(key, entry_type, fields)

    return out


def load(path: Path = VERIFIED_BIB) -> dict[str, Reference]:
    if not path.exists():
        return {}
    return parse_bibtex(path.read_text(encoding="utf-8"))


class CitationError(AssertionError):
    """A reference violates the integrity rules. Deliberately fatal."""


def check_structure(refs: dict[str, Reference]) -> list[str]:
    """Offline checks. Returns a list of problems; empty means clean."""
    problems: list[str] = []
    for key, ref in sorted(refs.items()):
        if not ref.provenance:
            problems.append(f"{key}: missing provenance field")
        elif ref.provenance not in PROVENANCE_TIERS:
            problems.append(
                f"{key}: provenance {ref.provenance!r} not one of {PROVENANCE_TIERS}"
            )
        if not ref.resolvable_url():
            problems.append(f"{key}: no doi and no url — cannot be verified")
        for required in ("title", "year"):
            if required not in ref.fields:
                problems.append(f"{key}: missing {required}")
    return problems


def _normalise_title(title: str) -> str:
    """Lowercase alphanumeric words, for tolerant title comparison."""
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", title.lower()).split())


def check_resolves(
    ref: Reference,
    *,
    timeout: int = 20,
    session: requests.Session | None = None,
) -> tuple[bool, str]:
    """Verify a reference exists and describes the work we think it does.

    For a DOI this uses **content negotiation** against doi.org rather than
    fetching the landing page. Publisher landing pages routinely return 403 to
    automated clients, so an HTTP status is a poor test of whether a DOI is real.
    Content negotiation returns registered metadata instead, which additionally
    lets us confirm the title matches.

    That second check matters more than the first. A fabricated DOI is easy to
    catch; a *real* DOI attached to the wrong paper is the failure mode that
    survives casual review, and it is exactly what an LLM produces when it
    half-remembers a reference.
    """
    session = session or requests.Session()
    session.headers.setdefault(
        "User-Agent",
        "tactical-football-analytics/0.1 (citation check; "
        "mailto:vidigalp@users.noreply.github.com)",
    )

    if ref.doi:
        try:
            response = session.get(
                f"https://doi.org/{ref.doi}",
                headers={"Accept": "application/vnd.citationstyles.csl+json"},
                timeout=timeout,
                allow_redirects=True,
            )
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            return False, f"{type(exc).__name__}: {exc}"

        if response.status_code >= 400:
            return False, f"DOI not registered (HTTP {response.status_code})"

        try:
            meta = response.json()
        except ValueError:
            return False, "DOI resolved but returned no metadata"

        registered = meta.get("title")
        if isinstance(registered, list):
            registered = registered[0] if registered else ""
        declared = ref.fields.get("title", "")

        if registered and declared:
            a, b = _normalise_title(registered), _normalise_title(declared)
            # Prefix match tolerates subtitle differences in either direction.
            if not (a.startswith(b[:60]) or b.startswith(a[:60])):
                return False, f"title mismatch — DOI registers {registered!r}"

        return True, "DOI registered, title matches"

    url = ref.url
    if url is None:
        return False, "no doi or url"

    try:
        response = session.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code >= 400:
            response = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        return response.status_code < 400, f"HTTP {response.status_code}"
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return False, f"{type(exc).__name__}: {exc}"


def assert_not_cited(keys: list[str], unverified: dict[str, Reference]) -> None:
    """Fail if published output cites anything from the quarantine file."""
    leaked = sorted(set(keys) & set(unverified))
    if leaked:
        raise CitationError(
            f"unverified references cited in published output: {leaked}. "
            "Verify them and move to references.bib, or remove the citation."
        )
