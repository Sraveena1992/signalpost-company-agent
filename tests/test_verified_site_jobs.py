from datetime import date, timedelta

from scripts.extract_company_site_jobs import observation, observations


def _profile():
    today = date.today()
    page_url = "https://nordlys.example/careers/developer"
    job = {
        "title": "Software Developer",
        "datePosted": (today - timedelta(days=2)).isoformat(),
        "validThrough": (today + timedelta(days=12)).isoformat(),
        "url": page_url,
        "hiringOrganization": {
            "name": "Nordlys Energi AS",
            "identifier": {"value": "123456785"},
        },
    }
    return {
        "organisation_number": "123456785",
        "name": "Nordlys Energi AS",
        "evidence": {"website": {
            "status": "available",
            "source_url": "https://nordlys.example/",
            "retrieved_at": today.isoformat(),
            "value": {
                "final_url": "https://nordlys.example/",
                "identity_assessment": {"publishable": True},
                "pages": [{
                    "url": page_url,
                    "content_sha256": "a" * 64,
                    "job_postings": [job, {**job, "title": "QA Developer", "url": page_url + "-qa"}],
                }],
            },
        }},
    }


def test_jobs_require_exact_registered_employer_and_fetched_posting():
    profile = _profile()
    jobs = observations(profile)
    assert len(jobs) == 2
    verified = next(item for item in jobs if item["source_url"].endswith("/developer"))
    assert verified["employer_verified"] is True
    assert verified["active_verified"] is True
    assert verified["expires_at"]
    linked_only = next(item for item in jobs if item["source_url"].endswith("developer-qa"))
    assert linked_only["active_verified"] is False


def test_jobs_do_not_verify_mismatching_or_unknown_employer_numbers():
    profile = _profile()
    posting = profile["evidence"]["website"]["value"]["pages"][0]["job_postings"][0]
    posting["hiringOrganization"]["identifier"] = {"value": "999999999"}
    assert observation(profile) is None
    posting["hiringOrganization"].pop("identifier")
    candidate = observation(profile)
    assert candidate is not None
    assert candidate["employer_verified"] is False


def test_jobs_expired_posting_is_rejected():
    profile = _profile()
    posting = profile["evidence"]["website"]["value"]["pages"][0]["job_postings"][0]
    posting["validThrough"] = (date.today() - timedelta(days=1)).isoformat()
    # The other linked posting still exists; the expired one must not appear.
    assert all(not item["source_url"].endswith("/developer") for item in observations(profile))
