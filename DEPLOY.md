# Deployment

The site is built by MkDocs and published by **Cloudflare Pages**. GitHub Pages remains configured
as a manual fallback, but does not deploy on push — two hosts publishing the same domain is a
reliable way to lose an afternoon to a stale page.

## Cloudflare Pages setup

**Workers & Pages → Create → Pages → Connect to Git → this repository.**

| Setting | Value |
|---|---|
| Production branch | `main` |
| Build command | `bash scripts/cf_build.sh` |
| Build output directory | `site` |
| Root directory | `/` |

No environment variables and no repository secrets are needed — Git integration authorises
Cloudflare directly, so there is no API token to store or rotate.

`scripts/cf_build.sh` installs `uv`, which downloads the pinned Python itself, so the site builds
against the same interpreter as local and CI rather than whatever the build image ships.

**The test suite runs inside the build command**, before `mkdocs`. A failure exits non-zero and
Cloudflare fails the deployment. This is the whole reason the build is a script: a repository whose
premise is that claims are verified before publication should not have a publish path that
bypasses its own verification. Network-marked tests, which resolve live DOIs, are excluded so a
registrar outage cannot block a deploy; `ci.yml` runs those on their own schedule.

Then **Custom domains → Set up a domain → `pedrovidigal.com`**, and add `www` as a redirect to the
apex. Because the domain is already in this Cloudflare account, DNS and TLS are configured
automatically — no grey-cloud compromise and no certificate provisioning wait.

## Why Cloudflare rather than GitHub Pages

Not capacity. The site is about 10 MB against a 1 GB ceiling either way.

- **Preview deployments per pull request.** The weekly workflow opens a draft PR; with previews
  that PR renders as a live site, figures included, before anyone merges it. Reviewing a study as
  raw Markdown is how a broken chart reaches production.
- **No DNS-only compromise.** GitHub Pages needs the Cloudflare proxy off, which means the CDN,
  caching and DDoS protection sit unused.
- **One vendor** for domain, DNS, hosting and analytics.

## Why Git integration rather than Direct Upload

Direct Upload deploys from a GitHub Actions job with `wrangler`, which is fully scriptable and
needs no dashboard step. It was rejected, and the reasoning is recorded because the first pass got
it wrong.

The argument for Direct Upload was that it puts the deploy downstream of `pytest`. That argument
is void: the same gate works here by running the tests inside the build command, as above.

What remains are three costs that compound:

- Direct Upload is a **one-way door** — Cloudflare's documentation states a project created that
  way can never switch to Git integration. Git integration is the reversible choice.
- It requires a **`CLOUDFLARE_API_TOKEN` and account ID stored as repository secrets**, in
  perpetuity, with rotation.
- **Fork pull requests cannot read repository secrets**, so previews would fail silently for
  outside contributors — which `CONTRIBUTING.md` invites.

## Redirects and headers

`scripts/cf_build.sh` writes `_redirects` and `_headers` into the built site.

Both mechanisms for keeping the original week-numbered URLs alive are present, deliberately.
`mkdocs-redirects` writes an HTML meta-refresh at each old path; `_redirects` declares a
server-side 301.

**Corrected against the live site.** An earlier version of this document claimed Cloudflare serves
an existing static asset in preference to a redirect rule, so the meta-refresh would be what fires.
Testing the deployed site showed the opposite: the 301 fires and the static stub is never reached.

The same test found the rules themselves were wrong. Cloudflare matched only the broad trailing
splats — `/weekly/*` and `/*` worked, while `/weekly/2026-W36/*` and `/studies/*/figures/*` never
did. Every archived week-numbered URL was landing on the studies index rather than its own study,
and figures were served `max-age=0` rather than the intended year. Both files are now generated
from `STUDY_SLUGS` with explicit paths and no wildcard except the final catch-all, and two tests
assert it.

A project whose premise is that cited artifacts stay reachable does not get to break its own
links, so the old `figures/` directories are left in place too. `tests/test_site.py` asserts every
published URL still resolves.

## Analytics

Cloudflare Web Analytics, enabled from **Analytics & Logs → Web Analytics**, with the token set as
`extra.cf_analytics_token` in `mkdocs.yml`. Cookie-free, so no consent banner is required.

## Falling back to GitHub Pages

Run the `pages` workflow manually, then point the domain back in **Settings → Pages**. The `CNAME`
file is still written on every build for exactly this reason.
