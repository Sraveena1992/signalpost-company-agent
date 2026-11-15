from scripts.extract_company_site_news import observation, observations


def _profile():
    excerpt = ("Nordlys Energi announces a published update for customers and partners. " * 3)
    page = lambda slug: {
        "url": "https://nordlys.example/nyheter/" + slug,
        "title": "Nordlys Energi announces " + slug,
        "published_at": "2026-11-10",
        "main_text_excerpt": excerpt,
        "article_like": True,
        "content_sha256": "a" * 64,
    }
    return {
        "organisation_number": "123456785",
        "name": "Nordlys Energi AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://nordlys.example/",
                "retrieved_at": "2026-11-15T00:00:00Z",
                "value": {
                    "final_url": "https://nordlys.example/",
                    "identity_assessment": {"publishable": True},
                    "pages": [
                        page("first-article"),
                        page("second-article"),
                        page("first-article"),
                        {**page("old-news"), "published_at": "2020-01-01"},
                        {**page("index"), "url": "https://nordlys.example/nyheter/"},
                    ],
                },
            }
        },
    }


def test_multi_article_news_deduplicates_and_keeps_original_single_item_contract():
    profile = _profile()
    items = observations(profile)
    assert len(items) == 2
    assert len({item["source_url"] for item in items}) == 2
    assert all(item["exact_entity"] and item["published_at"] for item in items)
    assert observation(profile) is not None


def test_multi_article_news_obeys_limit_and_rejects_unverified_website():
    profile = _profile()
    assert len(observations(profile, max_items=1)) == 1
    profile["evidence"]["website"]["value"]["identity_assessment"]["publishable"] = False
    assert observations(profile) == []
