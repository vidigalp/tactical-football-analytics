#!/usr/bin/env bash
# Cloudflare Pages build.
#
# The build image's own Python is irrelevant: uv downloads the interpreter this
# project pins, so the site builds against the same version as local and CI
# rather than whatever the platform happens to ship.
set -euo pipefail

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv sync --all-extras --dev
uv run python scripts/build_site.py
uv run mkdocs build --strict

# Server-side redirects and headers. mkdocs-redirects also emits HTML meta
# refreshes, which work everywhere; these are faster and return a real 301, so
# old links keep their search ranking instead of quietly losing it.
cat > site/_redirects <<'REDIRECTS'
/weekly/2026-W35/*  /studies/01-free-football-data/  301
/weekly/2026-W36/*  /studies/02-fouling-with-impunity/  301
/weekly/*           /studies/  301
REDIRECTS

cat > site/_headers <<'HEADERS'
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Permissions-Policy: geolocation=(), microphone=(), camera=()

# Figures and data are content-addressed by build; cache them hard.
/studies/*/figures/*
  Cache-Control: public, max-age=31536000, immutable
HEADERS

echo "built $(find site -type f | wc -l | tr -d ' ') files"
