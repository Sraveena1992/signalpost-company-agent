"""Exact registry source attribution and additional source-backed fields."""
from norway_company_agent.http import FetchResult
from norway_company_agent.official import fetch_official_modules, normalize_entity
from norway_company_agent.research import answer_profile


def test_additional_official_fields_are_normalized():
    body = {
        "organisasjonsnummer": "987654321",
        "navn": "Eksempel AS",
        "stiftelsesdato": "2010-02-03",
        "registreringsdatoEnhetsregisteret": "2010-03-04",
        "registrertIForetaksregisteret": True,
        "registrertIMvaregisteret": False,
        "registrertIFrivillighetsregisteret": False,
        "underTvangsavviklingEllerTvangsopplosning": False,
        "naeringskode2": {"kode": "62.020", "beskrivelse": "Consultancy"},
    }
    normalized = normalize_entity(body)
    assert normalized["established_at"] == "2010-02-03"
    assert normalized["registered_in_vat_register"] is False
    assert normalized["secondary_industry"]["kode"] == "62.020"


def test_live_values_are_cited_to_live_registry_not_older_bulk():
    live = {"field": "registry_live", "status": "available",
            "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/987654321",
            "retrieved_at": "2026-11-17T00:00:00Z"}
    bulk = {"field": "registry", "status": "available",
            "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
            "retrieved_at": "2026-10-01T00:00:00Z"}
    profile = {
        "organisation_number": "987654321", "name": "Eksempel AS",
        "bankrupt": False, "established_at": "2010-02-03",
        "registered_in_business_register": True,
        "registered_in_vat_register": False,
        "secondary_industry": {"kode": "62.020", "beskrivelse": "Consultancy"},
        "evidence": {"registry": bulk, "registry_live": live},
    }
    facts = answer_profile(profile, "status")
    names = {item["claim"]: item for item in facts["facts"]}
    assert names["Bankruptcy flag"]["value"] is False
    assert names["VAT Register registration flag"]["value"] is False
    assert names["Date established"]["value"] == "2010-02-03"
    assert names["Secondary industry"]["value"]["code"] == "62.020"
    assert all(item["source_url"] == live["source_url"] for item in facts["facts"])


def test_wrong_organisation_identity_is_quarantined():
    def wrong_fetch(url):
        return FetchResult(url=url, status=200, elapsed_ms=1, bytes_received=123,
                           body={"organisasjonsnummer": "111111111", "navn": "Different Entity AS"},
                           content_sha256="a" * 64, retrieved_at="2026-11-17T00:00:00Z")
    result, _ = fetch_official_modules("987654321", {"registry_live"}, fetcher=wrong_fetch)
    assert result["registry_live"]["status"] == "ambiguous"
    assert "does not match" in result["registry_live"].get("note", "").lower() or "differs" in result["registry_live"].get("note", "").lower()
