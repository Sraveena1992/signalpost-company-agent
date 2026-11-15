"""Publisher-visible Norwegian bylines take precedence over conflicting metadata."""
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
sys.path.insert(0,str(ROOT))
from bs4 import BeautifulSoup
from norway_company_agent.website import _published_date, _visible_article_date
from scripts.extract_company_site_news import observation


def test_norwegian_byline_without_deadline_confusion():
    html = """<html><head><meta property="article:published_time"
      content="2026-05-14T09:01:21+00:00"></head>
      <body><article><h1>Utlysning</h1><span>24 juli, 2026 av marius</span>
      <p>Send søknad innen 30.05.2026</p></article></body></html>"""
    soup=BeautifulSoup(html,"html.parser")
    assert _published_date(soup)[:10]=="2026-05-14"
    assert _visible_article_date(soup)=="2026-07-24"


def test_metadata_only_keeps_source_date_and_unknown_byline():
    soup=BeautifulSoup('<meta property="article:published_time" content="2026-05-14T09:01:21Z">',"html.parser")
    assert _visible_article_date(soup) is None
    assert _published_date(soup)[:10]=="2026-05-14"


def test_conflict_disclosed_within_valid_original_company_news():
    url="https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/"
    profile={"organisation_number":"987531630","name":"1. ÅS SPEIDERGRUPPE",
      "evidence":{"website":{"status":"available","source_url":"https://aas.speiding.no/",
       "retrieved_at":"2026-11-15T00:00:00Z",
       "value":{"final_url":"https://aas.speiding.no/",
        "identity_assessment":{"publishable":True,"score":100},
        "pages":[{"url":url,"title":"Utlysning: Sommerjobb som aktivitetsledere - 1. Ås speidergruppe",
          "published_at":"2026-07-24","published_at_metadata":"2026-05-14T09:01:21+00:00",
          "published_at_visible":"2026-07-24","publication_date_conflict":True,
          "article_like":True,
          "main_text_excerpt":("1. Ås speidergruppe arrangerer friluftsuker. "*8),
          "content_sha256":hashlib.sha256(b"evidence").hexdigest()}]}}}}
    x=observation(profile)
    assert x is not None
    assert x["published_at"]=="2026-07-24"
    assert x["metrics"]["publication_date_conflict"] is True
    assert x["metrics"]["publisher_metadata_date"].startswith("2026-05-14")
    assert x["signal_type"]=="public_post"  # Not falsely called active job

def test_source_audit_accepts_visible_author_date_not_conflicting_metadata():
    from pathlib import Path
    sys.path.insert(0,str(ROOT / "scripts"))
    from verify_all_claims_live import verify_publisher_date
    html = """<html><meta property="article:published_time" content="2026-05-14T09:01:21Z">
    <body><p>24 juli, 2026 av marius</p><p>Søknadsfrist 30.05.2026</p></body></html>"""
    assert verify_publisher_date(html,"2026-07-24") is True
    assert verify_publisher_date(html,"2026-05-14T09:01:21Z") is None
