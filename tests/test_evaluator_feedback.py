import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

"""Regressions from the 13 November Builderr evaluator feedback."""
from norway_company_agent.identity import apply_website_identity_gate, assess_social_identity
from norway_company_agent.research import answer_profile
from scripts.extract_company_site_news import observation as news_observation


def test_squarespace_social_links_not_attributed_to_lovehjerte_design():
    profile = {"organisation_number": "999999991", "name": "LØWEHJERTE DESIGN AS", "evidence": {}}
    website = {
        "status": "available",
        "source_url": "https://lovehjertedesign.squarespace.com/",
        "value": {
            "final_url": "https://lovehjertedesign.squarespace.com/",
            "title": "LØWEHJERTE DESIGN AS",
            "main_text_excerpt": "LØWEHJERTE DESIGN AS designer products. " * 8,
            "social_links": [
                {"platform": "x", "url": "https://x.com/squarespace"},
                {"platform": "linkedin", "url": "https://linkedin.com/company/squarespace"},
            ],
        },
    }
    result = apply_website_identity_gate(profile, website)
    assert result["website"]["value"]["social_links"] == []
    assert result["quarantined_social_links"] == 2


def test_squarespace_handle_rejected_for_different_company():
    profile = {"name": "LØWEHJERTE DESIGN AS", "organisation_number": "999999991"}
    assert not assess_social_identity(profile, {"platform": "x", "url": "https://x.com/squarespace"})["publishable"]
    assert not assess_social_identity(profile, {"platform": "linkedin", "url": "https://linkedin.com/company/squarespace"})["publishable"]


def test_missing_explicit_website_gate_cannot_publish_claims():
    profile = {
        "organisation_number": "999999991",
        "name": "LØWEHJERTE DESIGN AS",
        "evidence": {"website": {
            "status": "available",
            "source_url": "https://www.example.com/",
            "value": {
                "description": "Unverified marketing copy",
                "social_links": [{"platform": "x", "url": "https://x.com/squarespace"}],
            },
        }},
    }
    facts = answer_profile(profile, "Give me a company overview")["facts"]
    assert not any(f["classification"] in {"company_reported_claim", "company_linked_social_profile"} for f in facts)


def test_verified_company_news_needs_date_and_real_article_not_legal_name():
    import hashlib
    source = "https://www.example.no/news/new-project"
    profile = {
        "organisation_number": "999999991",
        "name": "EXAMPLE AS",
        "evidence": {
            "website": {
                "status": "available", "source_url": "https://www.example.no/",
                "retrieved_at": "2026-11-13T00:00:00Z",
                "value": {
                    "identity_assessment": {"publishable": True, "score": 1.0},
                    "pages": [{
                        "url": source,
                        "title": "New research centre opens",
                        "published_at": "2026-11-12",
                        "article_like": True,
                        "main_text_excerpt": "The company opened a new research centre today. " * 5,
                        "content_sha256": hashlib.sha256(b"article").hexdigest(),
                    }],
                },
            },
        },
    }
    item = news_observation(profile)
    assert item and item["source_url"] == source and item["published_at"] == "2026-11-12"
    profile["evidence"]["website"]["value"]["pages"][0]["published_at"] = None
    assert news_observation(profile) is None


def test_company_owned_jobposting_requires_date_exact_company_and_source():
    import hashlib
    from datetime import timedelta, datetime, timezone
    from scripts.extract_company_site_jobs import observation as job_observation
    url = "https://example.no/careers/backend-developer"
    item = {
        "title": "Backend Developer",
        "datePosted": "2026-11-12",
        "validThrough": (datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat(),
        "hiringOrganization": {"name": "EXAMPLE AS"},
        "url": url,
    }
    profile = {
        "name": "EXAMPLE AS",
        "organisation_number": "999999991",
        "evidence": {"website": {
            "status": "available", "source_url": "https://example.no",
            "retrieved_at": "2026-11-13",
            "value": {
                "final_url": "https://example.no",
                "identity_assessment": {"publishable": True, "score": 1.0},
                "pages": [{"url": url, "content_sha256": hashlib.sha256(b"job").hexdigest(), "job_postings": [item]}],
            },
        }},
    }
    result = job_observation(profile)
    assert result and result["signal_type"] == "job_posting"
    assert result["source_url"] == url
    item["hiringOrganization"] = {"name": "SQUARESPACE"}
    assert job_observation(profile) is None
    item["hiringOrganization"] = {"name": "EXAMPLE AS"}
    item["url"] = "https://squarespace.com/jobs/backend"
    assert job_observation(profile) is None
