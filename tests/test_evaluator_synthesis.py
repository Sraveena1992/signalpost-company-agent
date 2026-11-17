"""Evaluator-visible synthesis and conservative active vacancy publication."""
from datetime import date, timedelta

from norway_company_agent.batch import attach_synthesis, terminal_envelope
from norway_company_agent.research import answer_profile


def sample_profile():
    org = "987654321"
    registry = {"status": "available", "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/" + org,
                "retrieved_at": "2026-11-17T00:00:00Z", "value": {"organisation_number": org, "name": "Example AS"}}
    return {"organisation_number": org, "name": "Example AS",
            "evidence": {"registry_live": registry, "registry": registry,
                         "website": {"status": "not_found"}, "public_activity": {"status": "not_found"}}}


def test_terminal_envelope_exposes_existing_synthesis_at_root():
    profile = sample_profile()
    attach_synthesis(profile)
    envelope = terminal_envelope(profile, run_id="test",
                                 modules=["registry_live"], started_at="2026-11-17T00:00:00Z",
                                 completed_at="2026-11-17T00:00:01Z")
    assert envelope["synthesis"] == profile["synthesis"]
    brief = envelope["synthesis"]["decision_brief"]
    assert brief["identity"] == "Example AS"
    assert brief["verified_takeaway_count"] > 0
    assert all(item["source_url"] and item["retrieved_at"] for item in brief["verified_takeaways"])
    assert brief["evidence_gaps"]


def test_unverified_site_job_not_promoted_to_active_vacancy():
    profile = sample_profile()
    url = "https://example.no/careers/engineer"
    profile["evidence"]["website"] = {
        "status": "available", "source_url": "https://example.no/",
        "retrieved_at": "2026-11-17T00:00:00Z",
        "value": {"final_url": "https://example.no/",
                  "identity_assessment": {"publishable": True}}}
    job = {"signal_type": "job_posting", "exact_entity": True,
           "organisation_number": "987654321", "source_url": url,
           "retrieved_at": "2026-11-17T00:00:00Z",
           "published_at": (date.today() - timedelta(days=1)).isoformat(),
           "expires_at": (date.today() + timedelta(days=10)).isoformat(),
           "content_sha256": "a" * 64, "rights_status": "approved",
           "evidence_span": "Engineer", "employer_verified": False, "active_verified": False}
    profile["evidence"]["public_activity"] = {
        "status": "available", "value": {"observations": [job]}}
    assert not any(f["claim"] == "Verified company-site job posting"
                   for f in answer_profile(profile, "jobs")["facts"])
    job["employer_verified"] = True
    job["active_verified"] = True
    assert any(f["claim"] == "Verified company-site job posting"
               for f in answer_profile(profile, "jobs")["facts"])
    job["expires_at"] = "2020-01-01"
    assert not any(f["claim"] == "Verified company-site job posting"
                   for f in answer_profile(profile, "jobs")["facts"])
