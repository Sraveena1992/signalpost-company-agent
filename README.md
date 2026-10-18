# Signalpost — Norwegian Company Intelligence Agent

An evidence-first company research agent for Norwegian businesses. It combines official registry data, company website research, structured company records, and traceable source evidence into a reproducible batch-processing workflow.

**Core principle:** Every published company fact should be traceable to its source, linked to the correct legal entity, and distinguishable from information that could not be verified.

## Key capabilities

- **Entity resolution:** Uses the Norwegian organisation number as the primary identity anchor.
- **Official company data:** Retrieves available registry, financial, role, group, and workplace information.
- **Website research:** Checks registry-listed company websites while applying entity-matching safeguards.
- **Evidence traceability:** Records source information, retrieval timestamps, and content hashes.
- **Batch processing:** Processes organisation-number inputs and emits terminal JSONL envelopes.
- **Reliability:** Supports checkpoint/resume, validation, request metrics, and machine-readable run reports.
- **Refresh verification:** Compares saved profile snapshots to identify material changes and preserve evidence.
- **Conservative publication:** Avoids treating an unverified company or website match as established fact.

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

Inspect `out/refresh-demo.json` to review detected changes and supporting evidence.

## Validation

The local 100-company practice run recorded 100 terminal envelopes for 100 expected companies, passed the configured validation checks, and reported zero silent drops. The recorded run report includes request volume, transferred data, latency, and resumed profiles.

This is a local practice-run result, not an official competition score or qualification result.

## First run: try one saved example

Before downloading company data or running a full crawl, try the bundled public sample. It uses saved responses and does not require an API key, registry download, or live web requests.

```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-demo.json
```

Open `out/refresh-demo.json`. The `events` list shows changes between two versions of a company profile and the source evidence for each change. The sample is designed to check expected changes, false changes, and repeat-run stability.

The report's `qualification_passed` field refers only to the public sample check. It does not qualify an entry for the competition or prove live information coverage. Request counts from saved responses are not live network calls.

## Next: research live companies

This step downloads registry data and makes live requests. Use the official challenge instructions and permitted source policies before running a batch.

```bash
uv sync
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o signalpost-universe.jsonl.gz

uv run python select_entry_batch.py --universe signalpost-universe.jsonl.gz --count 100 --output entry-companies.jsonl

uv run python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --profiles-output out/smoke-profiles.jsonl --output out/smoke-envelopes.jsonl --report out/smoke-report.json --run-id smoke-001 --expected-count 100
```

The example above assumes the downloaded universe is available and that the selection command produces the expected JSONL input. Check the report and terminal output before treating a run as successful. Use only input batches and data sources permitted by the challenge.

Increase the batch size only after validating a smaller run. Builderr supplies the official evaluation batch; a local practice run is not an official score.

## The improvement loop

1. Treat the organisation number as the primary identity anchor.
2. Generate website and profile candidates from official data, the company site, lawful search providers, and named people.
3. Save each candidate and the evidence supporting or contradicting it.
4. Publish only exact-entity matches. Parent companies, brands, franchises, and similarly named businesses are not automatically the same entity.
5. Crawl static HTML first. Use a browser fallback only when a deterministic completeness check requires it.
6. Measure supported coverage, incorrect-company claims, runtime, requests, and cost.
7. Promote a strategy only when it improves coverage without weakening accuracy gates.
8. Freeze strategies and thresholds before an evaluation run.

The differentiator is external evidence that remains exact and auditable: official company pages, company-owned profiles, jobs, dated activity, and permitted public signals. Do not trade accuracy for volume.

## Important source rule

Open-source code does not grant permission to scrape a platform. Follow each source's terms, robots policy, rate limits, and licence. LinkedIn, Meta, and Indeed may be useful for discovery, but direct automated collection may be restricted. Use permitted APIs, licensed providers, company-owned links, or mark information as `blocked` or `not_available`.

Review `docs/competition-control-loop.md`, `docs/external-connectors.md`, and the relevant source policies before adding connectors.

## External-footprint orchestrator

The project includes an external-footprint orchestration step:

```bash
uv run python scripts/run_external_footprint.py --profiles out/smoke-profiles.jsonl --output out/smoke-external-observations.jsonl --report out/smoke-external-report.json
```

This layer is designed to promote observations only from websites that have passed the exact-entity identity gate. It records claim-level evidence, retrieval time, content hashes, rights status, and acquisition mode. Verify the actual run report before making claims about the results.

The observation file is an optimization artifact, not an official competition score. It must not be used to claim qualification without the required independent audit and evaluator-owned batch.

## Reproducibility and source responsibility

The project is designed for repeatable batch execution and auditable evidence collection. Live runs depend on the supplied input batch and required registry data. External sources must be accessed in accordance with their terms, licences, permissions, and rate limits.

## Submission contract

The submission should include:

- A 100-company smoke-test result or report.
- A documented command that accepts a JSONL batch of organisation numbers.
- Exactly one terminal envelope per input.
- Reproducible setup instructions and dependency information.
- Previous-snapshot input and material-change output.
- A machine-readable run report with runtime, request count, and third-party cost information.
- Declared models, APIs, licences, and source-rights assumptions.
