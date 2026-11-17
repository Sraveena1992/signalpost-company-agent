"""Bounded company website news discovery accepts relevant Norwegian sections.

New paths merely discover candidates. Original-source date and identity gates
remain mandatory before a claim can be published.
"""
from bs4 import BeautifulSoup

from norway_company_agent.website import _priority_links
from scripts.extract_company_site_news import observations


def test_priority_links_include_norwegian_press_article_blog_sections():
    soup = BeautifulSoup(
        '<nav><a href="/pressemeldinger/">Pressemeldinger</a>'
        '<a href="/artikler/">Artikler</a>'
        '<a href="/blogg/">Blogg</a></nav>', "html.parser"
    )
    links = _priority_links("https://example.no/", soup, limit=6)
    assert "https://example.no/pressemeldinger/" in links
    assert "https://example.no/artikler/" in links
    assert "https://example.no/blogg/" in links


def test_new_press_section_still_requires_source_date_and_exact_identity():
    profile = {
        "organisation_number": "987654321", "name": "Fjellkraft AS",
        "evidence": {"website": {
            "status": "available", "retrieved_at": "2026-11-17T00:00:00Z",
            "source_url": "https://fjellkraft.example/",
            "value": {"final_url": "https://fjellkraft.example/",
                      "identity_assessment": {"publishable": True},
                      "pages": [{
                          "url": "https://fjellkraft.example/pressemeldinger/utvidelse-2026",
                          "title": "Fjellkraft AS announces expansion",
                          "published_at": "2026-11-12",
                          "article_like": True,
                          "main_text_excerpt": ("Fjellkraft AS announces its plans. " * 10),
                          "content_sha256": "c" * 64,
                      }]},
        }},
    }
    assert len(observations(profile)) == 1
    profile["evidence"]["website"]["value"]["pages"][0]["published_at"] = ""
    assert observations(profile) == []
