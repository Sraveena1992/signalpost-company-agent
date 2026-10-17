# Signalpost — Norwegian Company Intelligence Agent

An evidence-first company research agent for Norwegian businesses. It combines official registry data, company website research, structured company records, and traceable source evidence into a reproducible batch-processing workflow.

**Core principle:** every published company fact should be traceable to its source, linked to the correct legal entity, and distinguishable from information that could not be verified.

## Key capabilities

- **Entity resolution:** uses the Norwegian organisation number as the primary identity anchor.
- **Official company data:** retrieves available registry, financial, role, group, and workplace information.
- **Website research:** checks registry-listed company websites while applying entity-matching safeguards.
- **Evidence traceability:** records source information, retrieval timestamps, and content hashes.
- **Batch processing:** processes organisation-number inputs and emits terminal JSONL envelopes.
- **Reliability:** supports checkpoint/resume, validation, request metrics, and machine-readable run reports.
- **Refresh verification:** compares saved profile snapshots to identify material changes and preserve evidence.
- **Conservative publication:** avoids treating an unverified company or website match as established fact.

## Quick start

Requirements: Python 3.12+ and `uv`.

Install project dependencies:

```bash
uv sync
```

Run the saved refresh-replay example without requiring live company data or an API key:

```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-demo.json
```

Inspect `out/refresh-demo.json` to review the detected changes and supporting evidence.

## Validation

The local 100-company practice run recorded 100 terminal envelopes for 100 expected companies, passed the configured validation checks, and reported zero silent drops. The run report records request volume, transferred data, latency, and resumed profiles.

This is a local smoke-test result, not an official competition score or qualification result.

## Reproducibility and source responsibility

The project is designed for repeatable batch execution and auditable evidence collection. Live runs depend on the supplied input batch and required registry data. External sources must be accessed in accordance with their terms, licences, permissions, and rate limits.

## First run: try one saved example

Requires Python 3.12+. Open a terminal inside this extracted folder.

Before downloading company data or running a full crawl, try the bundled public
sample. It uses saved responses: no API key, registry download or live web requests.

```bash
python3 scripts/run_refresh_replay.py \
  --manifest tests/fixtures/refresh-snapshots.json \
  --output out/refresh-demo.json
```

Open `out/refresh-demo.json`. The `events` list shows what changed between two
versions of one company profile and the source evidence for each change. The sample
should find two expected changes, no false changes, and no extra changes when the
same data is checked again.

The report's `qualification_passed` field refers only to this public sample check.
It does not qualify an entry for the competition or prove live information coverage.
The printed request counts are reads from saved responses, not network calls.

## Next: research live companies

Requires Python 3.12+ and `uv`. This step downloads data and makes live requests.
The manifest selector can create a local test batch of any size. Use 100 rows for the recommended smoke test before trying a larger batch.

```bash
uv sync
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o signalpost-universe.jsonl.gz

uv run python select_entry_batch.py \
  --universe signalpost-universe.jsonl.gz \
  --count 100 \
  --output entry-companies.jsonl

# Use the 100-company batch as your smoke test.
cp entry-companies.jsonl smoke-companies.jsonl

uv run python scripts/run_competition_batch.py \
  --organisations smoke-companies.jsonl \
  --bulk brreg-enheter.csv \
  --profiles-output out/smoke-profiles.jsonl \
  --output out/smoke-envelopes.jsonl \
  --report out/smoke-report.json \
  --run-id smoke-001 \
  --expected-count 100

# You may test at larger scale locally, but Builderr supplies the official batch for scoring.
uv run python scripts/run_competition_batch.py \
  --organisations entry-companies.jsonl \
  --bulk brreg-enheter.csv \
  --profiles-output out/profiles.jsonl \
  --output out/envelopes.jsonl \
  --report out/run-report.json \
  --run-id local-001 \
  --expected-count 1000

uv run --with pytest pytest -q
```

The published archive was clean-room verified on August 24, 2026: 104 tests and 5 subtests passed, followed by a one-company live BRREG smoke run with one terminal envelope, five requests and zero silent drops.

Increase `--count` and `--expected-count` together for a larger local test. The 100-row smoke test above is practice only; Builderr supplies the companies for every official run.

## The improvement loop

1. Treat the organisation number as the anchor.
2. Generate site/profile candidates from official data, the company site, lawful search providers and named people.
3. Save every candidate and the evidence for or against it.
4. Publish only exact-entity matches. Parent, brand, franchise and similarly named companies are not exact.
5. Crawl static HTML first. Escalate to a browser only when a deterministic completeness check fails.
6. Measure added supported coverage, wrong-company claims, runtime, requests and cost.
7. Promote a strategy only when it improves coverage without weakening the accuracy gates.
8. Freeze strategies and thresholds before the daily evaluation run.

The strongest differentiator is external evidence that remains exact and auditable: official company pages, company-owned profiles, jobs, dated activity, ratings/reviews and permitted public signals. Do not trade accuracy for volume.

## Important source rule

Open-source code does not grant permission to scrape a platform. Follow each source's terms, robots policy, rate limits and licence. LinkedIn, Meta and Indeed are useful identity/discovery targets, but direct automated collection may be restricted. Use permitted APIs, licensed providers, company-owned outbound links, or return `blocked`/`not_available`.

Read `docs/competition-control-loop.md`, `docs/external-connectors.md` and the public source policy before adding connectors.

## Submission contract

Submit a repository with:

- a 100-company smoke-test result or report;
- one documented command that accepts a JSONL batch of organisation numbers;
- exactly one terminal envelope per input;
- pinned dependencies and reproducible setup;
- a previous-snapshot input and material-change output;
- a machine-readable run report with runtime, request count and third-party cost;
- declared models, APIs, licences and source-rights assumptions.

Email the repository URL, run command, models/APIs and expected cost per 100-company run to `submit@builderr.ai`.

## External-footprint orchestrator

The starter now includes a conservative external-footprint orchestration step:

```bash
uv run python scripts/run_external_footprint.py \
  --profiles out/smoke-profiles.jsonl \
  --output out/smoke-external-observations.jsonl \
  --report out/smoke-external-report.json
```

This layer only promotes observations from a website that has already passed the exact-entity identity
 gate. It records claim-level evidence, retrieval time, content hashes, rights status and acquisition mode.
Unverified sites produce no external publication. The layer is deliberately provider-neutral so approved
API/licensed connectors can be added and measured without weakening the publication gate.

The resulting observation file is an optimization artifact; it is not an official competition score and
must not be used to claim qualification without the required independent audit and evaluator-owned batch.
