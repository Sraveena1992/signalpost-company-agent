"""Regression tests for the NAV job-feed exact-org workflow: no network needed."""
from datetime import datetime, timezone, timedelta

import pytest
from scripts.run_nav_feed_500 import enrich, nav_url, qualify


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ORG = "987654321"


def ad(uid="a1", status="ACTIVE", modified="2026-11-14T00:00:00Z"):
    return {"url": "/api/v1/feedentry/" + uid, "date_modified": modified,
            "_feed_entry": {"uuid": uid, "status": status}}


def detail(uid="a1", org=ORG, status="ACTIVE", expires="2026-11-20T00:00:00Z"):
    return {"uuid": uid, "status": status,
            "json": {"uuid": uid, "title": "Engineer", "published": "2026-11-01T00:00:00Z",
                     "expires": expires, "employer": {"orgnr": org, "name": "Company"},
                     "sourceurl": "https://arbeidsplassen.nav.no/stillinger/stilling/abc"}}


def make_get(pages, details):
    def get(url, token, **kwargs):
        if url.endswith("/api/v1/feed"):
            return pages[0]
        if url.endswith("/api/v1/feed/next"):
            return pages[1]
        return details[url.rsplit("/", 1)[-1]]
    return get


def test_exact_org_and_active():
    pages = [{"items": [ad("a1"), ad("a2")], "next_url": None}]
    profiles = [{"organisation_number": ORG}, {"organisation_number": "123456789"}]
    result, report = enrich(profiles, get=make_get(pages, {"a1": detail(), "a2": detail("a2", "111111111")}),
                            token="fixture", now=NOW)
    assert report["verified_active_jobs"] == 1
    assert report["matched_companies"] == 1
    assert report["scan_complete"] is True
    assert result[0]["evidence"]["nav_jobs"]["status"] == "available"
    assert result[1]["evidence"]["nav_jobs"]["status"] == "not_found"
    assert report["rejected"]["not_in_batch"] == 1


def test_inactive_newer_update_removes_prior_active():
    pages = [{"items": [ad("a1"), ad("a1", "INACTIVE", "2026-11-14T03:00:00Z")], "next_url": None}]
    result, report = enrich([{"organisation_number": ORG}],
                            get=make_get(pages, {"a1": detail()}), token="fixture", now=NOW)
    assert report["verified_active_jobs"] == 0
    assert report["active_ads_examined"] == 0


def test_incomplete_scan_does_not_claim_no_jobs():
    pages = [{"items": [], "next_url": "/api/v1/feed/next"}]
    result, report = enrich([{"organisation_number": ORG}], get=make_get(pages, {}),
                            token="fixture", max_pages=1, now=NOW)
    assert report["scan_complete"] is False
    assert result[0]["evidence"]["nav_jobs"]["status"] == "source_error"


def test_invalid_employer_and_expired():
    assert qualify(detail(org="111111111"), ORG, NOW)[1] == "employer_orgnr_mismatch"
    assert qualify(detail(expires="2026-11-10T00:00:00Z"), ORG, NOW)[1] == "stale_or_expired"
    assert qualify(detail(status="INACTIVE"), ORG, NOW)[1] == "inactive_detail"


def test_url_security():
    for url in ["http://pam-stilling-feed.nav.no/api/v1/feed",
                "https://evil.test/api/v1/feed",
                "//evil.test/api/v1/feed",
                "/api/v1/../admin",
                "https://abc@pam-stilling-feed.nav.no/api/v1/feed"]:
        with pytest.raises(ValueError):
            nav_url(url)


def test_duplicate_orgs_rejected():
    with pytest.raises(ValueError):
        enrich([{"organisation_number": ORG}, {"organisation_number": ORG}],
               get=make_get([], {}), token="fixture", now=NOW)


def test_500_company_contract():
    numbers = [f"{i:09d}" for i in range(500)]
    profiles = [{"organisation_number": n, "evidence": {"registry": {"status": "available"}}} for n in numbers]
    result, report = enrich(profiles, get=make_get([{"items": [], "next_url": None}], {}),
                            token="fixture", now=NOW)
    assert report["companies"] == 500
    assert report["verified_active_jobs"] == 0
    assert len(result) == 500
    assert all(item["evidence"]["registry"]["status"] == "available" for item in result)


def test_date_and_link_requirements():
    bad = detail()
    bad["json"]["sourceurl"] = "javascript:alert(1)"
    assert qualify(bad, ORG, NOW)[1] == "unsafe_source_url"
    missing = detail()
    del missing["json"]["expires"]
    assert qualify(missing, ORG, NOW)[1] == "missing_dates"


def test_nav_detail_failure_never_proves_no_jobs():
    pages = [{"items": [ad("a1")], "next_url": None}]
    def unavailable(url, token, **kwargs):
        if url.endswith("/api/v1/feed"):
            return pages[0]
        raise OSError("network unavailable")
    result, report = enrich([{"organisation_number": ORG}], get=unavailable,
                            token="fixture", now=NOW)
    assert report["scan_complete"] is False
    assert result[0]["evidence"]["nav_jobs"]["status"] == "source_error"
    assert report["rejected"]["detail_fetch_or_parse_failure"] == 1
