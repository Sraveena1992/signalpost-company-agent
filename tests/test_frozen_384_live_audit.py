"""Frozen sample source recheck must not use invented AI gold labels."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_frozen_384_live import match_frozen, audit
from scripts.build_blind_gold_review import build_queue
import pytest


def fixtures():
    profiles=[]
    for i in range(500):
        org=f"{i:09d}"
        profiles.append({
            "organisation_number":org,
            "name":f"Test {i} AS",
            "evidence":{"registry_live":{"source_url":"https://data.brreg.no/enhetsregisteret/api/enheter/"+org}},
            "synthesis":{"facts":[{"claim":"Organisation number","value":org,
                     "classification":"official_registry_fact",
                     "source_url":"https://data.brreg.no/enhetsregisteret/api/enheter/"+org,
                     "retrieved_at":"2026-11-14T00:00:00Z"}]},
        })
    return profiles


def test_fake_live_rechecks_and_unknowns_never_human_certified():
    profiles=fixtures()
    queue,_=build_queue(profiles,sample_size=384)
    def controlled(url,_):
        org=url.split("/")[-1]
        if int(org) % 10 == 0:
            return {"state":"unavailable"}
        return {"state":"available","body":{"organisasjonsnummer":org}}
    rows,summary=audit(queue,profiles,fetch_function=controlled,workers=4)
    assert len(rows)==384
    assert summary["machine_source_verdict_counts"]["unverifiable"]>0
    assert summary["human_gold_labels"]==0
    assert summary["certified_human_95pct"] is False
    assert summary["independent_ai_gold_label_certified"] is False
    assert all(r["independent_human_gold_label"] is None for r in rows)


def test_rejects_original_sample_tampering():
    profiles=fixtures()
    queue,_=build_queue(profiles,sample_size=384)
    queue[0]["claimed_source_url"]="https://example.invalid/another-company"
    with pytest.raises(ValueError,match="source mismatch"):
        match_frozen(queue,profiles)


def test_rejects_incomplete_historic_input():
    profiles=fixtures()
    queue,_=build_queue(profiles,sample_size=384)
    with pytest.raises(ValueError,match="exactly 500"):
        match_frozen(queue,profiles[:-1])
