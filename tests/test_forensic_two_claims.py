import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.forensic_two_open_claims import extract_raw_evidence, TARGETS

def test_norwegian_date_visible_but_not_gold_label():
    raw = b'<html><h1>Utlysning</h1><p>24 juli, 2026 av marius</p></html>'
    x = extract_raw_evidence(raw)
    assert any("24 juli" in date for date in x["article_visible_dates"])

def test_company_description_metadata_preserved():
    raw = b'<meta name="description" content="first responder equipment">'
    x = extract_raw_evidence(raw)
    assert {"field":"description","value":"first responder equipment"} in x["meta"]

def test_only_whitelisted_original_source_urls():
    assert set(TARGETS) == {"995311321", "987531630"}
    assert all(url.startswith("https://") for url in TARGETS.values())
