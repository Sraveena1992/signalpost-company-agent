# Signalpost — Company Intelligence Agent

**Evidence-first Norwegian company research, built for verifiable facts and reproducible batch evaluation.**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Web%20Demo-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-111%20passing-brightgreen)](#testing-and-validation)
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
| Research modules | Registry, accounting obligations, financials, roles, group, locations and website research |
| Batch safeguards | Duplicate-input checks, terminal-state checks and exact organisation membership validation |
| Web interface | Lightweight live official-registry lookup prototype |
| API | JSON company lookup and health endpoint |
| Test suite | 111 tests passed in the latest recorded CI run |

## Live demo and verification

**Local web interface**

Run the application locally and open:

- Web interface: http://127.0.0.1:8000
- Interactive API documentation: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/healthz

These addresses work on the developer's computer only. They are **not public deployment URLs**.

**Health check**

The local health endpoint returned:

```json
{
  "status": "ok",
  "service": "signalpost-company-agent"
}
```

This confirms that the local application responded successfully at the time of testing. It does not establish public availability.

**Public deployment:** To be added after the Render deployment succeeds.

## How it works

### 1. Establish company identity

Use the Norwegian organisation number as the primary identifier and consult official registry information before associating evidence with a company.

### 2. Collect and organise evidence

The research pipeline contains modules for registry information, accounting obligations, financial information, roles, group relationships, locations and website research.

### 3. Preserve provenance

The project structures evidence and records source information so that retrieved facts can be traced and reviewed. Search results or name similarity alone should not be treated as proof of company identity.

### 4. Validate batch output

The batch workflow checks expected output counts and company membership, alongside other validation checks. Missing, duplicated or unexpected company identifiers should not silently pass validation.

### 5. Present results

The lightweight web prototype provides an official-registry lookup for a single Norwegian organisation number. The broader research pipeline remains available through the CLI.

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

The web prototype is a separate, lightweight entry point for live registry lookups. It should not be confused with the complete batch research workflow.

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

### Start the web prototype

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

The batch runner is available at [`scripts/run_competition_batch.py`](scripts/run_competition_batch.py).

To see its supported options:

```powershell
uv run python scripts/run_competition_batch.py --help
```

Use the official challenge input and its prescribed run instructions for an evaluation run. Do not substitute a self-selected list when the evaluation requires a supplied batch.

The project also includes batch utilities in [`src/norway_company_agent/batch.py`](src/norway_company_agent/batch.py) and regression tests in [`tests/test_poc.py`](tests/test_poc.py).

## Testing and validation

The last recorded local test run completed with:

- **111 tests passed**
- 11 warnings
- 7 subtests passed
- `git diff --check` returned no whitespace errors

These are local development results, not an official Builderr score or an independently verified competition result. Rerun the commands above to confirm the current working tree.

The local practice smoke report is available at [`out/smoke-report.json`](out/smoke-report.json), if that file is present in the checkout. A local smoke report is not an official evaluation result.

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

- The web interface currently demonstrates a single-company official-registry lookup.
- It is not a complete hosted dashboard for every research module.
- A successful health check verifies service responsiveness, not research accuracy.
- Registry fields may be missing or change over time.
- The local smoke test is not the official competition evaluation.
- Public hosting and deployment health must be verified separately before a public URL is advertised.
- Performance, cost per official run and competition scores should be reported only when measured or confirmed.

## Project status

**Prototype in active development.** The goal is to make company research more traceable, reproducible and robust against wrong-company matches and incomplete batch outputs.

**Maintainer:** Raveena Sharma
**Repository:** https://github.com/Sraveena1992/signalpost-company-agent
