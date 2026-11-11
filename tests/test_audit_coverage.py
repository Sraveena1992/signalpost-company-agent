import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_coverage import audit


def test_count_resumed_separately():
    report = {
        "run_id": "example",
        "input_count": 100,
        "emitted_envelopes": 100,
        "resumed_profiles": 60,
        "profiles_fetched_this_run": 40,
        "validation": {"passed": True, "checks": {"exact_expected_count": True}},
    }
    result = audit(report)
    assert result["count"]["resumed"] == 60
    assert result["count"]["fetched_this_run"] == 40
    assert result["contract_pass"] is True


def test_module_coverage_and_missing_provenance():
    rows = [{
        "synthesis": {"unsupported_or_uncertain": ["jobs"]},
        "evidence": {
            "website": {"state": "available", "source_url": "https://example.org", "retrieved_at": "2026-11-06"},
            "roles": {"state": "blocked"},
            "group": {"state": "available"},
        },
    }]
    result = audit({"input_count": 1}, rows)["profile_audit"]
    assert result["module_state_counts"]["roles:blocked"] == 1
    assert result["available_evidence_missing_source_or_timestamp"] == [{"row": 0, "module": "group"}]
    assert result["unsupported_or_uncertain_items"] == 1
