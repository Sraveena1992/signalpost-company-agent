# NAV job vacancy feed — isolated Signalpost integration

Source: https://navikt.github.io/pam-stilling-feed/

This feature is **off by default**. It does not change existing company-site
jobs/news extraction, registry facts, or production behavior.

## Authentication

The NAV API requires a bearer JWT, even for the experimental public token.
For permitted production use, register as a NAV consumer, accept the terms,
and request a private token. Never commit or print the token.

On PowerShell (example using an authorized token kept outside source control):

```powershell
$env:NAV_FEED_TOKEN = Read-Host "NAV feed bearer token"
```

## Extend the exact existing 500-company run

Use the same exact membership input and all existing CLI arguments, add:

```text
--nav-feed --nav-max-pages 250 --nav-max-details 10000
```

`nav_job_feed` is included in the run report; each enriched profile receives
`evidence.nav_jobs`, which is separate from company-owned `public_activity`.

Alternatively, enrich an already-completed 500-company profile artifact:

```powershell
uv run python scripts/run_nav_feed_500.py `
  --profiles artifacts/full-500/profiles-500.jsonl `
  --output artifacts/nav-500/profiles-with-jobs.jsonl `
  --report artifacts/nav-500/nav-job-report.json `
  --max-pages 250 --max-details 10000
```

The original input is never overwritten. `nav_jobs.status=available` means
a source-backed ACTIVE vacancy was associated with exact employer.orgnr;
`not_found` requires a complete scan; `source_error` means incomplete
and **never implies absence of jobs**.

## Matching and evidence

- Consume NAV feed event pages and resolve the most recent update per vacancy UUID.
- Ignore INACTIVE, expired, implausibly stale, and future postings.
- Fetch each ACTIVE vacancy detail from NAV's documented endpoint.
- Require exact **nine-digit employer.orgnr** equality with the supplied company,
  not title/name similarity.
- Preserve NAV source URL, original vacancy URL, timestamps and expiry.
- If coverage is bounded by max pages/detail requests, report it as incomplete.
- Do not publish phone/email/contact details from feed records.

## Live experiment

The isolated workflow
`.github/workflows/nav-experimental-jobs.yml` uses NAV's documented
experimental public token and existing 500-company CI artifact. It limits
requests deliberately and must not be interpreted as a complete national
vacancy census or an official Builderr score.

NAV itself states its feed has **no employer-filtered query**, so a complete
national active-job index requires consuming current change events and retaining
the latest status per UUID. Tokens may rotate; official terms govern reuse.

## Tests

```powershell
uv run pytest -q tests/test_nav_feed_500.py
uv run pytest -q
```

Do not merge into main or deploy before reviewing CI and source-access terms.
