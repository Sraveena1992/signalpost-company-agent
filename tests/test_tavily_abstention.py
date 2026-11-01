from pathlib import Path

def test_tavily_abstention_has_explicit_evidence():
    source = Path("scripts/run_competition_batch.py").read_text(
        encoding="utf-8"
    )
    assert '"website_discovery", "not_found"' in source
    assert "candidate_attempts" in source
    assert "No candidate passed independent company website identity verification." in source
