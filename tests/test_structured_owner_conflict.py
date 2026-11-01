from norway_company_agent.identity import assess_website_identity


def test_article_mention_does_not_prove_subsidiary_website_ownership():
    profile = {
        "organisation_number": "916340257",
        "name": "WYSSEN NORGE AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://www.wyssenavalanche.com/en/norway-story/",
                "value": {
                    "final_url": "https://www.wyssenavalanche.com/en/norway-story/",
                    "title": "Wyssen Norge AS successful in Norway",
                    "description": "Wyssen Norge AS worked as subcontractor.",
                    "main_text_excerpt": "Wyssen Norge AS worked as subcontractor. " * 6,
                    "structured_organisations": [
                        {"@type": "Organization", "name": "Wyssen Avalanche Control AG"}
                    ],
                },
            }
        },
    }
    result = assess_website_identity(profile)
    assert result["publishable"] is False
    assert result["status"] != "exact"
    assert "structured publisher organisation differs" in result["reasons"][0]


def test_matching_structured_owner_remains_eligible():
    profile = {
        "organisation_number": "916340257",
        "name": "WYSSEN NORGE AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://example.org/",
                "value": {
                    "final_url": "https://example.org/",
                    "title": "WYSSEN NORGE AS",
                    "description": "WYSSEN NORGE AS official company site",
                    "main_text_excerpt": "Company details and services. " * 8,
                    "structured_organisations": [
                        {"@type": "Organization", "name": "WYSSEN NORGE AS"}
                    ],
                },
            }
        },
    }
    assert assess_website_identity(profile)["publishable"] is True
