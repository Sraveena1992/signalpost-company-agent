from datetime import date, timedelta

from norway_company_agent.research import answer_profile


def test_exact_nav_job_is_source_linked_and_expiry_bounded():
    expiry = (date.today() + timedelta(days=10)).isoformat()
    job = {
        "organisation_number": "987654321",
        "title": "Engineer",
        "status": "active_at_retrieval",
        "source_class": "nav_official_job_feed",
        "source_url": "https://arbeidsplassen.nav.no/stillinger/stilling/abc",
        "nav_source_url": "https://pam-stilling-feed.nav.no/api/v1/feedentry/a1",
        "retrieved_at": date.today().isoformat(),
        "expires_at": expiry,
    }
    profile = {"organisation_number": "987654321", "name": "Example Company",
               "evidence": {"nav_jobs": {"status": "available", "value": {"postings": [job]}}}}
    result = answer_profile(profile, "jobs")
    matches = [fact for fact in result["facts"] if fact["claim"] == "NAV job marked active at retrieval"]
    assert len(matches) == 1
    assert matches[0]["source_url"] == job["nav_source_url"]
    assert matches[0]["retrieved_at"] == job["retrieved_at"]
    profile["evidence"]["nav_jobs"]["value"]["postings"][0] = {**job, "organisation_number": "000000000"}
    assert not any(f["claim"] == "NAV job marked active at retrieval" for f in answer_profile(profile, "jobs")["facts"])
    profile["evidence"]["nav_jobs"]["value"]["postings"][0] = {**job, "expires_at": "2020-01-01"}
    assert not any(f["claim"] == "NAV job marked active at retrieval" for f in answer_profile(profile, "jobs")["facts"])
