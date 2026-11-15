"""Builderr v2 refresh: data outage is not a material company change."""
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from norway_company_agent.refresh import diff_profile
from norway_company_agent.batch import attach_synthesis


def specimen():
    return {"organisation_number":"923609016","name":"EQUINOR ASA",
            "evidence":{"registry":{"status":"available",
                   "source_url":"https://data.brreg.no/enhetsregisteret/api/enheter/923609016",
                   "retrieved_at":"2026-11-15T04:00:00Z"},
             "financials":{"status":"available",
                           "source_url":"https://example.test/original-financial-source",
                           "retrieved_at":"2026-11-14T04:00:00Z",
                           "content_sha256":"a"*64,
                           "value":{"records":[{"period":"2025","revenue":100}]}}}}


def test_failed_fetch_not_false_financial_change():
    old=specimen()
    new=copy.deepcopy(old)
    new["evidence"]["financials"]={"status":"source_error"}
    assert not any(x["field"]=="financials.records" for x in diff_profile(old,new))
    attach_synthesis(new,old)
    assert new["synthesis"]["change_status"]=="no_material_changes"
    assert any(x["topic"]=="normalized annual accounts" for x in new["synthesis"]["unknowns"])


def test_changed_financial_records_keep_old_and_new_evidence():
    old=specimen()
    new=copy.deepcopy(old)
    new["evidence"]["financials"]["value"]["records"][0]["revenue"]=120
    new["evidence"]["financials"]["retrieved_at"]="2026-11-15T05:00:00Z"
    new["evidence"]["financials"]["content_sha256"]="b"*64
    changes=diff_profile(old,new)
    fact=next(x for x in changes if x["field"]=="financials.records")
    assert fact["previous_source_url"]=="https://example.test/original-financial-source"
    assert fact["previous_retrieved_at"]=="2026-11-14T04:00:00Z"
    assert fact["old_content_sha256"]=="a"*64
    assert fact["new_content_sha256"]=="b"*64


def test_registry_value_zero_still_valid_real_change():
    old=specimen()
    old["employees"]=None
    new=copy.deepcopy(old)
    new["employees"]=0
    changes=diff_profile(old,new)
    assert any(x["field"]=="registry.employees" and x["new_value"]==0 for x in changes)
