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
