#!/usr/bin/env bash
# Cloudflare Pages build command.
#
# The test suite runs here, before the site is built, and a failure exits
# non-zero so Cloudflare fails the deployment. That gate is the reason this is
# a script rather than an inline `mkdocs build`: a repository whose premise is
# that claims are verified before publication should not have a publish path
# that bypasses its own verification.
#
# The build image's own Python is irrelevant. uv downloads the interpreter this
# project pins, so the site builds against the same version as local and CI.
set -euo pipefail

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv sync --all-extras --dev

# Network-marked tests resolve live DOIs. They are excluded here so a registrar
# outage cannot block a deploy; ci.yml runs them on their own schedule.
uv run ruff check .
uv run pytest -m "not network"

uv run python scripts/build_site.py
uv run mkdocs build --strict

echo "built $(find site -type f | wc -l | tr -d ' ') files"
