"""Gold review queue: no circular labels, deterministic category coverage."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_blind_gold_review import build_queue, evaluate_adjudicated
import pytest


def sample_profiles():
    rows = []
    for n in range(500):
        org = f"{n:09d}"
        facts = [
            {"claim": "Registered name", "value": f"EXAMPLE {n}", "classification": "official_registry_fact",
             "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/" + org, "retrieved_at": "2026-11-14"},
            {"claim": "Registered role", "value": "Director", "classification": "official_role_record",
             "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/" + org, "retrieved_at": "2026-11-14"},
        ]
        rows.append({"organisation_number": org, "name": f"EXAMPLE {n}", "synthesis": {"facts": facts}})
    return rows


def test_exact_fixed_sample_and_no_gold_labels():
    a, meta = build_queue(sample_profiles(), 384)
    b, _ = build_queue(sample_profiles(), 384)
    assert a == b
    assert len(a) == 384
    assert len({r["claim_id"] for r in a}) == 384
    assert all(r["review"]["status"] == "UNREVIEWED" for r in a)
    assert not meta["is_gold_labelled"]
    assert meta["category_sample_counts"]["official_role_record"] >= 10


def test_prevents_circular_evaluation_without_independent_review():
    queue, meta = build_queue(sample_profiles(), 20)
    with pytest.raises(ValueError, match="unreviewed"):
        evaluate_adjudicated(queue, meta)


def test_fails_if_source_not_independent_or_wrong_org():
    queue, meta = build_queue(sample_profiles(), 10)
    for item in queue:
        item["review"] = {
            "status": "VERIFIED_TRUE", "reviewer": "independent_review_01",
            "reviewer_notes": "Checked original source", "independent_source_retrieved_at": "2026-11-14T00:00:00Z",
            "independent_primary_source_url": item["claimed_source_url"],
            "independently_verified_company_orgnr": "000000999"}
    with pytest.raises(ValueError, match="exact independent organisation"):
        evaluate_adjudicated(queue, meta)


def test_no_auto_recall_or_official_score():
    queue, meta = build_queue(sample_profiles(), 10)
    for item in queue:
        item["review"] = {
            "status": "VERIFIED_TRUE", "reviewer": "independent_review_01",
            "reviewer_notes": "Checked original source", "independent_source_retrieved_at": "2026-11-14T00:00:00Z",
            "independent_primary_source_url": item["claimed_source_url"],
            "independently_verified_company_orgnr": item["organisation_number"]}
    result = evaluate_adjudicated(queue, meta)
    assert result["recall"] is None
    assert result["official_builderr_score"] is None
    assert result["independent_95pct_certified"] is False
