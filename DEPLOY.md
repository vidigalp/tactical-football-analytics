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

No environment variables are needed. The build script installs `uv`, which downloads the pinned
Python itself, so the site builds against the same interpreter as local and CI rather than
whatever the build image ships.

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

## Redirects and headers

`scripts/cf_build.sh` writes `_redirects` and `_headers` into the built site.

Both mechanisms for keeping the original week-numbered URLs alive are present, deliberately.
`mkdocs-redirects` writes an HTML meta-refresh at each old path; `_redirects` declares a
server-side 301. Cloudflare serves an existing static asset in preference to a redirect rule, so
in practice the meta-refresh is what fires today — the rules are the fallback if those stubs are
ever pruned from the build.

A project whose premise is that cited artifacts stay reachable does not get to break its own
links, so the old `figures/` directories are left in place too. `tests/test_site.py` asserts every
published URL still resolves.

## Analytics

Cloudflare Web Analytics, enabled from **Analytics & Logs → Web Analytics**, with the token set as
`extra.cf_analytics_token` in `mkdocs.yml`. Cookie-free, so no consent banner is required.

## Falling back to GitHub Pages

Run the `pages` workflow manually, then point the domain back in **Settings → Pages**. The `CNAME`
file is still written on every build for exactly this reason.
