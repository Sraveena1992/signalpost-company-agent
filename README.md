# Signalpost — Company Intelligence Agent

**Evidence-first Norwegian company research, built for verifiable facts and reproducible batch evaluation.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Web%20Demo-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-contract%20checked-brightgreen)](#testing-and-validation)
[![Status](https://img.shields.io/badge/Status-Prototype-orange)](#scope-and-limitations)

**Repository:** https://github.com/Sraveena1992/signalpost-company-agent

> Signalpost is designed to identify Norwegian companies, collect evidence from permitted sources, preserve source provenance, and produce structured outputs that can be checked and rerun.

## At a glance

| Capability | Current implementation |
|---|---|
| Official registry research | Brønnøysund Register Centre integration |
| Batch processing | CLI runner with expected-count validation |
| Evidence handling | Structured evidence and source metadata |
| Company identity | Conservative identity checks |
| Research modules | Registry, accounting obligations, financials, filing history, roles, group, locations, website identity and company-owned site activity |
| Batch safeguards | Duplicate-input checks, terminal-state checks and exact organisation membership validation |
| Public web interface | Company-name/number search plus on-demand single-company evidence research |
| API | JSON company lookup and health endpoint |
| Automated regression suite | Latest recorded successful run: 123 tests and 7 subtests |

## Live demo

- **Public web app:** https://signalpost-company-agent.onrender.com/
- **API documentation:** https://signalpost-company-agent.onrender.com/docs
- **Health endpoint:** https://signalpost-company-agent.onrender.com/healthz
- **Example official record:** https://data.brreg.no/enhetsregisteret/api/enheter/912900584

The public interface accepts a company name or nine-digit Norwegian organisation number and requests live results from the official Brønnøysund Register API. From a selected company record, the **Run evidence research** action invokes the same batch research pipeline for that company and displays source-linked synthesis, module states, evidence, and the run report.

The public web demo supports **single-company registry search plus on-demand evidence research**. It does not provide a hosted 100-company batch dashboard, and the default pipeline still lacks a permitted external job-posting connector. It does not claim to verify every company fact, social account, news item, job posting, or financial result.

A successful health response confirms service responsiveness only; it does not establish research accuracy or an official competition score. Public hosting may be subject to cold starts or temporary availability issues.

## How it works

### 1. Establish company identity

Use the Norwegian organisation number as the primary identifier and consult official registry information before associating evidence with a company.

### 2. Collect and organise evidence

The research pipeline contains modules for registry information, accounting obligations, financial information, roles, group relationships, locations and website research.

### 3. Preserve provenance

The project structures evidence and records source information so retrieved facts can be traced and reviewed. Search results or name similarity alone should not be treated as proof of company identity.

### 4. Validate batch output

The batch workflow checks expected output counts and company membership, alongside other validation checks. Missing, duplicated or unexpected company identifiers should not silently pass validation.

### 5. Present results

The lightweight public web prototype provides a live official-registry lookup for one Norwegian organisation number. The broader research pipeline is run through the CLI and supporting scripts, not through the public web interface.

## Architecture

```text
Organisation numbers
        |
        v
Input validation
        |
        v
Official registry / research modules
        |
        v
Evidence and source metadata
        |
        v
Structured company profiles
        |
        v
Batch validation and reports
```

The public web prototype is a lightweight entry point for live registry search and one-company research; the reproducible multi-company workflow remains available through the CLI. The default batch includes company-owned website activity when the bounded crawl yields dated, identity-gated evidence. A permitted, reproducible external job-posting connector is not yet integrated into the default batch runner; do not claim full jobs coverage until that connector and its source rights are verified.

## Quick start

### Requirements

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)
- Network access for live registry lookups

### Install dependencies

```powershell
uv sync --frozen
```

### Run tests

```powershell
uv run pytest -q
```

### Start the web prototype locally

```powershell
uv run uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in your browser.

### API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Company lookup interface |
| `GET /api/company/{orgnr}` | JSON response for an organisation number |
| `GET /docs` | Interactive API documentation |
| `GET /healthz` | Application health check |

The company lookup uses the official registry endpoint:

https://data.brreg.no/enhetsregisteret/api/enheter/

For example, the API route is `/api/company/{orgnr}`, where `{orgnr}` is a nine-digit Norwegian organisation number.

## Batch runner

The batch runner is available at [`scripts/run_competition_batch.py`](scripts/run_competition_batch.py). It accepts the evaluator-provided batch file, infers its count by default (so batches can grow beyond 100), and emits one terminal envelope for each input.

### One-command batch run

After installing locked dependencies and placing the supplied organisation-number file at `data/organisations.jsonl`, run:

```powershell
uv run python scripts/run_competition_batch.py --organisations data/organisations.jsonl --output artifacts/terminal-results.jsonl --profiles-output artifacts/profiles.jsonl --report artifacts/run-report.json --run-id signalpost-final
```

The optional `--bulk path/to/brreg-snapshot.csv` flag seeds profiles from a frozen official registry snapshot; without it, the runner starts from the live Brønnøysund API. The input file is evaluator-owned and must not be replaced with a hard-coded company list. For the required 100-company smoke test, the repository now includes `scripts/run_100_company_smoke.py`. It downloads the official Brønnøysund entity snapshot, selects a deterministic sample of 100 active organisations with 2025 annual-account records, runs the real batch CLI, and writes terminal results, profiles, and a JSON run report. GitHub Actions workflow [`100-company-smoke.yml`](.github/workflows/100-company-smoke.yml) runs this check and uploads those files as an artifact. The sample is a local smoke test only, not Builderr's official scoring batch.

The public terminal-state vocabulary is exactly: `available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, and `failed`. Internal fetch states are mapped to this vocabulary before output. The validator checks the expected count, unique IDs, exact input membership, allowed entity/module states, and source URL plus retrieval time for available evidence. A per-company exception is emitted as an explicit failed state rather than silently dropping that input.

Every profile also includes a deterministic `synthesis` object with source-linked facts and an `unsupported_or_uncertain` list. To compare against a prior profile snapshot, pass `--previous-profiles artifacts/previous-profiles.jsonl`; the run emits a `changes` list and marks the baseline honestly as `no_previous_snapshot`, `no_material_changes`, or `changes_detected`. Re-running against unchanged facts should not invent a change.

The project also includes batch utilities in [`src/norway_company_agent/batch.py`](src/norway_company_agent/batch.py) and regression tests in [`tests/test_poc.py`](tests/test_poc.py).

## Testing and validation

The latest confirmed GitHub Actions regression run passed **123 tests and 7 subtests**:

https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/39905813739

The suite includes evidence provenance, identity gates, company research modules, refresh behaviour, and the Builderr terminal-state contract. Check Actions again after later code changes.

A passing test suite is not a substitute for the required 100-company live smoke test or an official Builderr score.


## Evaluation contract mapping

| Builderr public terminal state | Signalpost mapping |
|---|---|
| `available` | Fact/evidence was retrieved and published |
| `not_available` | Explicitly checked but no matching fact was found |
| `blocked` | Source refused access or robots/policy prevented retrieval |
| `not_applicable` | The question does not apply to this company |
| `ambiguous` | Candidate/company identity could not be confirmed safely |
| `failed` | A source, module, or per-company run failed |

Each module state is mapped to this public vocabulary. Missing input companies, duplicate IDs, unexpected IDs, invalid states, and output-count mismatches are reported by the validator. The same source snapshot should not create duplicate observations or false changes; refresh comparisons require the exact same organisation number and dataset membership.

## Models, APIs, cost, and licence notes

- **Models:** no LLM/model API is used by the default competition batch command.
- **APIs/sources:** official Brønnøysund Register Centre endpoints and company public websites where available.
- **Declared direct third-party API/model cost:** USD $0.00 per default run because the default modules make no paid model/API calls. This excludes hosting, bandwidth, and general infrastructure and should be rechecked if paid connectors are added.
- **Dependencies:** pinned by `uv.lock`; review each dependency's upstream licence before redistributing a packaged build. This repository does not claim that every transitive dependency has been separately legal-audited.
- **Secrets:** the default batch runner requires no personal-account API credential. Never commit credentials or private keys.

## Data sources and evidence policy

- **Official registry:** [Brønnøysund Register Centre](https://www.brreg.no/en/)
- **Registry API:** https://data.brreg.no/enhetsregisteret/api/enheter/
- **Python:** https://www.python.org/
- **uv:** https://docs.astral.sh/uv/
- **FastAPI:** https://fastapi.tiangolo.com/

The system should distinguish verified facts from unavailable or unconfirmed information, retain source references, and avoid presenting inferred associations as confirmed facts. Source availability and completeness can vary.

## Reproducibility

The repository contains dependency configuration in `pyproject.toml` and `uv.lock`. Run the tests and inspect generated reports before submitting a revision.

Do not commit private API keys, credentials, or large local registry downloads. Optional integrations may require separate configuration.

## Scope and limitations

- The public web interface currently demonstrates a single-company official-registry lookup.
- It is not a complete hosted dashboard for every research module.
- A successful health check verifies service responsiveness, not research accuracy.
- Registry fields may be missing or change over time.
- The local smoke test is not the official competition evaluation.
- Batch research and structured reports must be verified separately from the public web demo.
- Performance, cost per official run and competition scores should be reported only when measured or confirmed.

## Project status

**Prototype in active development.** The goal is to make company research more traceable, reproducible and robust against wrong-company matches and incomplete batch outputs.

**Maintainer:** Raveena Sharma  
**Repository:** https://github.com/Sraveena1992/signalpost-company-agent
