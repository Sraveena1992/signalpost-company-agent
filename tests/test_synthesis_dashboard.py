"""Reviewer-facing decision synthesis must be visible, sourced and safe."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_decision_brief_and_provenance():
    text = (ROOT / "static" / "signalpost_dashboard.js").read_text(encoding="utf-8")
    assert "data.synthesis || p.synthesis" in text
    assert "brief.verified_takeaways" in text
    assert "brief.evidence_gaps" in text
    assert "brief.next_verification_steps" in text
    assert "brief.change_assessment" in text
    assert "link(item.source_url,'Inspect source')" in text
    assert "cell(item.retrieved_at)" in text
    assert "['Synthesis'," in text


def test_dashboard_discloses_missing_synthesis_without_inventing_it():
    text = (ROOT / "static" / "signalpost_dashboard.js").read_text(encoding="utf-8")
    assert "No reviewer-visible decision brief was returned" in text
    assert "No open vacancy or missing financial information is inferred" in text
    assert "esc(brief.executive_summary" in text
