"""The published URLs must keep resolving.

Studies were renamed from week numbers to slugs after Week 2 was already public.
Anything that was linked from a post, an abstract or a citation has to survive
that, so the redirect map is checked rather than trusted: a target that no
longer exists produces a redirect to a 404, which is worse than no redirect.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"

#: URLs that have been published somewhere we cannot edit — social posts, the
#: repository README, anything already cited. Adding a study means adding its
#: old path here if it ever shipped under a different one.
PUBLISHED_PATHS = ("weekly/2026-W35.md", "weekly/2026-W36.md")


def redirect_maps() -> dict[str, str]:
    """Parse the redirect_maps block without importing mkdocs' loader.

    mkdocs.yml uses `!!python/name:` tags, which PyYAML's safe loader rejects,
    and the unsafe loader is not worth pulling in for four lines of mapping.
    """
    text = MKDOCS.read_text()
    block = re.search(r"redirect_maps:\n((?:\s+#.*\n|\s+\S+\.md:\s*\S+\.md\n)+)", text)
    assert block, "redirect_maps block not found in mkdocs.yml"
    pairs = re.findall(r"^\s+(\S+\.md):\s*(\S+\.md)$", block.group(1), re.M)
    return dict(pairs)


@pytest.mark.parametrize("old", PUBLISHED_PATHS)
def test_published_url_has_a_redirect(old: str) -> None:
    assert old in redirect_maps(), f"{old} was published and now has no redirect"


@pytest.mark.parametrize("old,new", sorted(redirect_maps().items()))
def test_redirect_target_exists(old: str, new: str) -> None:
    """Requires docs/ to have been assembled first.

    docs/ is generated and gitignored, so on a clean checkout this cannot run
    until `scripts/build_site.py` has been executed. A Cloudflare deploy failed
    on exactly that, passing locally only because docs/ was already populated
    from an earlier run.
    """
    assert DOCS.exists(), (
        "docs/ has not been generated -- run `python scripts/build_site.py` first"
    )
    assert (DOCS / new).exists(), f"{old} redirects to {new}, which does not exist"


def test_cname_is_written_by_the_build() -> None:
    """The apex breaks silently if CNAME drifts out of the published site."""
    source = (ROOT / "scripts" / "build_site.py").read_text()
    assert 'pedrovidigal.com' in source and 'CNAME' in source


def test_cloudflare_build_script_matches_documented_settings() -> None:
    """DEPLOY.md tells a human what to type into the dashboard; keep it true."""
    body = (ROOT / "scripts" / "cf_build.sh").read_text()
    assert "bash scripts/cf_build.sh" in (ROOT / "DEPLOY.md").read_text()
    assert "mkdocs build --strict" in body, "a warning must fail the deploy, not ship"


def test_deploy_is_gated_on_the_test_suite() -> None:
    """The only thing making Git integration safe here.

    Cloudflare builds independently of CI, so without this line a deploy ships
    on a red test suite. Losing it would be silent, hence the test.
    """
    body = (ROOT / "scripts" / "cf_build.sh").read_text()
    assert "set -euo pipefail" in body, "a failing test must abort the build"

    # Commands only: the header comment names `mkdocs build` while explaining
    # why this gate exists, and ordering must be judged on what actually runs.
    commands = [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    ran = "\n".join(commands)
    assert 'pytest -m "not network"' in ran
    assert ran.index("pytest") < ran.index("mkdocs build"), "gate must precede the build"
    # docs/ is generated, so assembly has to happen before the tests read it.
    assert ran.index("build_site.py") < ran.index("pytest"), (
        "build_site.py must run before pytest, or tests that read docs/ fail on a clean clone"
    )


def test_server_rules_are_emitted_by_the_python_build() -> None:
    """Cloudflare reads these from the site root; mkdocs copies them from docs/."""
    body = (ROOT / "scripts" / "build_site.py").read_text()
    assert '"_redirects"' in body and '"_headers"' in body
