"""Exact-company jobs and diagnostic invariants for the immutable 500 batch."""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scripts.extract_company_site_jobs import observation
from scripts.diagnose_exact_500_jobs import run, diagnostic


def fixture(hiring):
    date = datetime.now(timezone.utc).date()
    url = "https://example.no/jobs/example"
    return {
        "organisation_number": "123456789",
        "name": "EXAMPLE AS",
        "evidence": {
            "website": {
                "status": "available", "source_url": "https://example.no",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "value": {
                    "final_url": "https://example.no",
                    "identity_assessment": {"publishable": True, "score": 1},
                    "pages": [{
                        "url": url, "content_sha256": hashlib.sha256(b"job").hexdigest(),
                        "job_postings": [{
                            "title": "Engineer", "datePosted": date.isoformat(),
                            "validThrough": (date + timedelta(days=21)).isoformat(),
                            "hiringOrganization": hiring, "url": url,
                        }],
                    }],
                },
            },
            "public_activity": {"status": "not_found"},
        },
    }


def test_missing_employer_must_not_publish_job():
    assert observation(fixture({})) is None
    assert observation(fixture({"name": "PARENT CORPORATION"})) is None


def test_exact_employer_and_legal_identifier():
    assert observation(fixture({"name": "EXAMPLE AS"})) is not None
    assert observation(fixture({"name": "EXAMPLE AS", "identifier": {"value": "123456789"}})) is not None
    assert observation(fixture({"name": "EXAMPLE AS", "identifier": {"value": "987654321"}})) is None


def test_diagnostic_never_confuses_ats_leads_with_openings():
    row = fixture({"name": "EXAMPLE AS"})
    page = row["evidence"]["website"]["value"]["pages"][0]
    page["article_and_job_links"] = ["https://jobs.teamtailor.com/example"]
    x = diagnostic(row)
    assert x["jobposting_jsonld_candidates"] == 1
    assert x["verified_site_jobs"] == 0
    assert x["status"] == "structured_candidates_not_accepted"


def test_exact_input_500_unique_and_zero_not_absence():
    sample = fixture({"name": "EXAMPLE AS"})
    rows = [{**sample, "organisation_number": f"{i:09d}"} for i in range(500)]
    out, summary = run(rows)
    assert len(out) == 500
    assert summary["verified_jobs"] == 0
    assert "NOT a new live" in summary["claim_boundary"]
