"""Strict company-owned noticeboard evidence: dated article yes, expired job no."""
import hashlib
import sys
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from norway_company_agent.website import _priority_links
from scripts.extract_company_site_news import observation


def _profile(*, title="Utlysning: Sommerjobb som aktivitetsledere - 1. Ås speidergruppe", path="/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/", published=None, approved=True):
    url = "https://aas.speiding.no" + path
    return {
        "organisation_number": "987531630",
        "name": "1. ÅS SPEIDERGRUPPE",
        "evidence": {"website": {
            "status": "available", "source_url": "https://aas.speiding.no/",
            "retrieved_at": "2026-11-14T00:00:00Z",
            "value": {
                "final_url": "https://aas.speiding.no/",
                "identity_assessment": {"publishable": approved, "score": 100, "method": "official_site"},
                "pages": [{
                    "url": url, "title": title,
                    "published_at": published or date.today().isoformat(),
                    "article_like": True,
                    "main_text_excerpt": ("1. Ås speidergruppe organiserer en sommeraktivitet. " * 7),
                    "content_sha256": hashlib.sha256(b"article fixture").hexdigest(),
                }]
            }
        }}
    }


def test_homepage_discovery_accepts_norwegian_noticeboard():
    soup = BeautifulSoup('<a href="/oppslagstavle/">Oppslagstavla</a>', "html.parser")
    assert "https://aas.speiding.no/oppslagstavle/" in _priority_links("https://aas.speiding.no/", soup)


def test_date_and_exact_organisation_noticeboard_item_is_valid():
    p = _profile()
    result = observation(p)
    assert result is not None
    assert result["signal_type"] == "public_post"
    assert result["source_url"].startswith("https://aas.speiding.no/oppslagstavle/")
    assert result["organisation_number"] == "987531630"


def test_noticeboard_index_is_not_claim():
    assert observation(_profile(path="/oppslagstavle/")) is None


def test_wrong_entity_and_unverified_site_blocked():
    assert observation(_profile(approved=False)) is None
    assert observation(_profile(title="Unrelated", path="/oppslagstavle/unrelated/",
                                published=date.today().isoformat(),
                                )) is not None  # identity is checked against substantive article text
    bad = _profile()
    bad["evidence"]["website"]["value"]["pages"][0]["title"] = "Unrelated event"
    bad["evidence"]["website"]["value"]["pages"][0]["main_text_excerpt"] = "An unrelated group" * 12
    assert observation(bad) is None


def test_undated_stale_and_future_not_accepted():
    for timestamp in ("", "2017-01-01", (date.today() + timedelta(days=5)).isoformat()):
        bad = _profile()
        bad["evidence"]["website"]["value"]["pages"][0]["published_at"] = timestamp
        assert observation(bad) is None


def test_external_host_rejected():
    bad = _profile()
    bad["evidence"]["website"]["value"]["pages"][0]["url"] = "https://elsewhere.no/oppslagstavle/valid-item"
    assert observation(bad) is None


def test_homepage_shows_source_linked_dated_example_without_claiming_active_vacancy():
    from app import home
    html = home().body.decode("utf-8")
    assert 'id="verified-company-update"' in html
    assert "https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/" in html
    assert "987531630" in html
    assert "Active vacancy: not verified" in html
    assert 'rel="noopener noreferrer"' in html
