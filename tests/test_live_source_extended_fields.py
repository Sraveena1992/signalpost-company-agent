"""Source-recheck assertions must use exact company and original-source facts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_all_claims_live import compare_registry, compare_annual_copy_year, check_claim


def test_extended_registry_claims_require_live_field_match():
    body = {
        "organisasjonsnummer": "894198362",
        "navn": "1314981 ONTARIO LIMITED",
        "organisasjonsform": {"kode": "UTLA"},
        "forretningsadresse": {
            "adresse": ["60 Hanson Road Unit 128"],
            "poststed": "LB 2P6 MISSISSAUGA ONTARIO",
            "land": "Canada",
        },
        "stiftelsesdato": "2007-01-01",
        "registrertIMvaregisteret": False,
        "naeringskode2": {"kode": "62.020", "beskrivelse": "Consultancy"},
    }
    org = "894198362"
    assert compare_registry("Registered business address",
        "60 Hanson Road Unit 128, LB 2P6 MISSISSAUGA ONTARIO, Canada", body, org) is True
    assert compare_registry("Legal form", "UTLA", body, org) is True
    assert compare_registry("VAT Register registration flag", False, body, org) is True
    assert compare_registry("Date established", "2007-01-01", body, org) is True
    assert compare_registry("Secondary industry",
        {"code": "62.020", "description": "Consultancy"}, body, org) is True
    assert compare_registry("Date established", "2008-01-01", body, org) is False
    assert compare_registry("Date established", "2007-01-01", body, "999999999") is False
    assert compare_registry("Liquidation flag", False, body, org) is None
    assert compare_registry("Municipality", "OSLO", body, org) is None


def test_filing_copy_index_only_accepts_exact_org_and_observed_year():
    org = "987654321"
    url = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/987654321/aar"
    assert compare_annual_copy_year("Annual accounts copy listed for year", "2024",
                                   [2022, 2024, 2025], url, org) is True
    assert compare_annual_copy_year("Annual accounts copy listed for year", "2023",
                                   [2022, 2024, 2025], url, org) is None
    assert compare_annual_copy_year("Annual accounts copy listed for year", "2024",
                                   [2024], url, "111111111") is None
    assert compare_annual_copy_year("Annual accounts copy listed for year", "2024",
                                   {"years": [2024]}, url, org) is None


def test_copy_year_claim_classification_preserves_missing_unknown():
    url = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/987654321/aar"
    fact = {"claim": "Annual accounts copy listed for year", "value": "2024",
            "classification": "official_annual_copy_index",
            "source_url": url, "retrieved_at": "2026-11-17T00:00:00Z"}
    assert check_claim(fact, "987654321", {url: {"state": "available", "body": [2024]}})[0] == "confirmed"
    assert check_claim(fact, "987654321", {url: {"state": "available", "body": [2025]}})[0] == "unverifiable"
    assert check_claim(fact, "987654321", {url: {"state": "unavailable"}})[0] == "unverifiable"
