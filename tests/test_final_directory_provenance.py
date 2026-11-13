"""A real-company source audit and 300-record registry directory regression gates."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import app
from scripts.audit_claim_provenance import audit
from scripts.verify_registry_directory import verified_record, verify


def test_directory_three_official_pages_and_source_links(monkeypatch):
    requests = []
    def response(url):
        requests.append(url)
        return {"_embedded": {"enheter": [{
            "organisasjonsnummer": "923609016",
            "navn": "EQUINOR ASA",
            "organisasjonsform": {"beskrivelse": "Allmennaksjeselskap"},
        }]}}
    monkeypatch.setattr(app, "_get_json", response)
    for page in range(3):
        result = app.browse_registry_page(page=page, size=100)
        assert result["page"] == page
        assert result["results"][0]["registry_source"].endswith("/923609016")
        assert f"page={page}" in requests[-1]
    with pytest.raises(ValueError):
        app.browse_registry_page(page=3)


def test_company_verifier_requires_matching_exact_official_identity(monkeypatch):
    from scripts import verify_registry_directory as verifier
    monkeypatch.setattr(verifier, "fetch_json", lambda _: {
        "organisasjonsnummer": "923609016", "navn": "EQUINOR ASA",
        "organisasjonsform": {"beskrivelse": "Allmennaksjeselskap"}
    })
    result = verified_record({"organisasjonsnummer": "923609016", "navn": "EQUINOR ASA"})
    assert result["organisation_number"] == "923609016"
    assert result["verification"].startswith("exact official")
    assert result["registry_source"].endswith("/923609016")
    with pytest.raises(ValueError, match="disagrees"):
        verified_record({"organisasjonsnummer": "923609016", "navn": "SQUARESPACE"})


def test_audit_detects_cross_company_financial_claim(tmp_path):
    path=tmp_path/"profile.jsonl"
    path.write_text(__import__("json").dumps({
        "organisation_number": "923609016", "name": "EQUINOR ASA",
        "evidence": {"financials": {"status": "available",
          "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/923609016",
          "retrieved_at": "2026-11-13T12:00:00Z"}},
        "synthesis": {"facts": [{
            "claim": "Annual result", "value": 1,
            "classification": "official_annual_account",
            "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/984851006",
            "retrieved_at": "2026-11-13T12:00:00Z",
        }]},
    })+"\n",encoding="utf-8")
    result=audit(path)
    assert result["counts"]["claims"] == 1
    assert any("mismatch" in flag["reason"].lower() for flag in result["flags"])


def test_workspace_autoloads_300_live_records():
    page=(ROOT/"static"/"intelligence.html").read_text(encoding="utf-8")
    assert "for(let page=0;page<3;page++)" in page
    assert "Browse 300 Norwegian registry companies" in page
    assert "await loadDirectory(false)" in page
    assert "id=\"sortDirectory\"" in page
    assert "id=\"filterDirectory\"" in page
