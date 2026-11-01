from unittest.mock import patch

from scripts.run_tavily_discovery import discover

PROFILE = {
    "name": "EXAMPLE COMPANY AS",
    "organisation_number": "123456789",
    "municipality": "Oslo",
}

SEARCH_RESULT = [{
    "url": "https://example.com/about",
    "title": "EXAMPLE COMPANY AS",
    "snippet": "Organisation number 123456789",
    "rank": 1,
    "provider": "tavily",
}]

CANDIDATE = {
    "url": "https://example.com/about",
    "score": 10,
    "publishable_candidate": True,
}

WEBSITE = {
    "status": "available",
    "source_url": "https://example.com/about",
}

METRICS = {
    "requests": 2,
    "bytes": 500,
    "latencies_ms": [100, 200],
}

GATED = {
    "website": {
        "status": "available",
        "source_url": "https://example.com/about",
    },
    "assessment": {"publishable": True},
}


def test_discovery_reuses_verified_record():
    with (
        patch("scripts.run_tavily_discovery.search", return_value=SEARCH_RESULT),
        patch("scripts.run_tavily_discovery.score_search_candidate", return_value=CANDIDATE),
        patch("scripts.run_tavily_discovery.fetch_website", return_value=(WEBSITE, METRICS)) as fetch,
        patch("scripts.run_tavily_discovery.apply_website_identity_gate", return_value=GATED),
    ):
        result = discover(PROFILE, "fake-test-key")

    assert result["status"] == "verified"
    assert result["website_record"] == GATED["website"]
    assert result["crawl_metrics"] == METRICS
    fetch.assert_called_once()


def test_discovery_preserves_metrics_when_no_candidate_verifies():
    rejected = {
        "website": {"status": "ambiguous"},
        "assessment": {"publishable": False},
    }

    with (
        patch("scripts.run_tavily_discovery.search", return_value=SEARCH_RESULT),
        patch("scripts.run_tavily_discovery.score_search_candidate", return_value=CANDIDATE),
        patch("scripts.run_tavily_discovery.fetch_website", return_value=(WEBSITE, METRICS)),
        patch("scripts.run_tavily_discovery.apply_website_identity_gate", return_value=rejected),
    ):
        result = discover(PROFILE, "fake-test-key")

    assert result["status"] == "not_verified"
    assert result["crawl_metrics"]["requests"] == 2
    assert result["crawl_metrics"]["bytes"] == 500
