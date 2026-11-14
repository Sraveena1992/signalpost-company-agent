"""Review evidence tests: publisher-owned dated articles and changed metadata."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_all_claims_live import check_company_news, check_claim, verify_publisher_date

URL = "https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/"
NEWS = {"published_at": "2026-05-14T09:01:21+00:00",
        "headline_or_role": "Utlysning: Sommerjobb som aktivitetsledere"}
HTML = """<html><head>
<meta property="article:published_time" content="2026-05-14T09:01:21+00:00">
<meta property="og:title" content="Utlysning: Sommerjobb som aktivitetsledere - 1. Ås speidergruppe">
</head><body><article>Utlysning: Sommerjobb som aktivitetsledere</article></body></html>"""


def test_real_original_publisher_date_and_title_prove_article():
    assert verify_publisher_date(HTML, NEWS["published_at"]) is True
    assert check_company_news(URL, NEWS, HTML) is True


def test_undated_article_is_unverifiable_not_confirmed():
    assert check_company_news(URL, NEWS, "<title>Utlysning: Sommerjobb som aktivitetsledere</title>") is None


def test_mismatched_date_does_not_become_a_positive():
    assert check_company_news(URL, NEWS, HTML.replace("2026-05-14", "2026-05-15")) is None


def test_index_and_unrelated_domain_not_accepted():
    assert check_company_news("https://aas.speiding.no/oppslagstavle/", NEWS, HTML) is False
    assert check_company_news("https://aas.speiding.no/other-thing/", NEWS, HTML) is False


def test_description_change_requires_adjudication_instead_of_false_positive():
    fact = {"claim": "Website description", "classification": "company_reported_claim",
            "value": "Historical description", "source_url": "https://www.1hjelp.no/",
            "retrieved_at": "2026-11-14T10:00:00+00:00"}
    checked = {"https://www.1hjelp.no/": {"state": "available_html",
        "text": '<meta name="description" content="New website description">'}}
    state, reason = check_claim(fact, "995311321", checked)
    assert state == "unverifiable", (state, reason)
    checked["https://www.1hjelp.no/"]["text"] = '<meta name="description" content="Historical description">'
    assert check_claim(fact, "995311321", checked)[0] == "confirmed"


def test_news_claim_needs_original_article_publisher_metadata():
    fact = {"claim": "Verified company-site news", "classification": "verified_company_site_news",
            "value": NEWS, "source_url": URL, "retrieved_at": "2026-11-14T10:00:00+00:00"}
    assert check_claim(fact, "987531630", {URL: {"state": "available_html", "text": HTML}})[0] == "confirmed"
    assert check_claim(fact, "987531630", {URL: {"state": "available_html", "text": "<html>Article only</html>"}})[0] == "unverifiable"


def test_wrong_company_site_host_is_rejected_before_confirming_claim():
    fact = {"claim": "Verified company-site news", "classification": "verified_company_site_news",
            "value": NEWS, "source_url": URL, "retrieved_at": "2026-11-14T10:00:00+00:00"}
    fresh = {URL: {"state": "available_html", "text": HTML}}
    assert check_claim(fact, "987531630", fresh,
                       {"987531630": {"aas.speiding.no"}})[0] == "confirmed"
    state, why = check_claim(fact, "111111111", fresh,
                            {"111111111": {"other.no"}})
    assert (state, why) == ("contradicted", "wrong_company_source_host")

def test_missing_live_registry_fields_cannot_contradict_historical_claims():
    from verify_all_claims_live import compare_registry
    raw = {"organisasjonsnummer": "932850753", "navn": "2 NK SOLUTION SP. Z O.O. SP. K"}
    assert compare_registry("Bankruptcy flag", False, raw, "932850753") is None
    assert compare_registry("Liquidation flag", False, raw, "932850753") is None
    assert compare_registry("Registered business address", "ul. Dluga 25, Polen", raw, "932850753") is None
    assert compare_registry("Bankruptcy flag", False, {**raw, "konkurs": False}, "932850753") is True
    assert compare_registry("Bankruptcy flag", False, {**raw, "konkurs": True}, "932850753") is False
    # Wrong company remains a contradiction, not an unknown.
    assert compare_registry("Bankruptcy flag", False, raw, "111111111") is False
