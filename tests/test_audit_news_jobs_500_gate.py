"""Coverage gate regression tests (no network required)."""
from scripts.audit_news_jobs_500_gate import evaluate


def _row(org, *, checked=True, status="not_available", observations=None):
    return {"organisation_number": org, "checked": checked, "status": status, "observations": observations or []}


def test_all_checked_with_no_news_is_complete_search_not_news_count():
    ids = ["123456789", "987654321"]
    report = evaluate(ids, [_row(x) for x in ids])
    assert report["structural_pass"]
    assert report["coverage_percent"] == 100.0
    assert report["candidate_observations"] == 0


def test_missing_company_blocks_pass():
    report = evaluate(["123456789", "987654321"], [_row("123456789")])
    assert not report["structural_pass"]
    assert report["missing_company_count"] == 1


def test_duplicate_company_blocks_pass():
    report = evaluate(["123456789"], [_row("123456789"), _row("123456789")])
    assert not report["structural_pass"]


def test_unverified_news_not_treated_as_independently_checked():
    item = {"source_url": "https://example.org/news", "retrieved_at": "2026-11-14T00:00:00Z", "evidence_span": "News title"}
    report = evaluate(["123456789"], [_row("123456789", status="available", observations=[item])])
    assert report["source_provenance_complete_candidates"] == 1
    assert report["self_reported_independently_checked_candidates_not_gold_validated"] == 0


def test_wrong_entity_claim_blocks_pass():
    item = {"organisation_number": "999999999", "source_url": "https://example.org/news", "retrieved_at": "2026-11-14", "evidence_span": "Title"}
    report = evaluate(["123456789"], [_row("123456789", status="available", observations=[item])])
    assert not report["structural_pass"]
