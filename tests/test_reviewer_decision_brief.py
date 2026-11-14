"""Decision-useful synthesis must remain anchored in original source metadata."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from norway_company_agent.batch import attach_synthesis


def test_decision_brief_contains_only_source_linked_supported_takeaways():
    row={
       "organisation_number":"999999991",
       "name":"EXAMPLE AS",
       "industry":{"beskrivelse":"Computer programming","kode":"62.010"},
       "evidence":{
         "registry":{"status":"available",
                     "source_url":"https://data.brreg.no/enhetsregisteret/api/enheter/999999991",
                     "retrieved_at":"2026-11-14T00:00:00Z",
                     "value":{"navn":"EXAMPLE AS"}},
         "website":{"status":"ambiguous"},
         "financials":{"status":"not_found"},
         "public_activity":{"status":"not_found"},
       }
    }
    attach_synthesis(row)
    brief=row["synthesis"]["decision_brief"]
    assert brief["identity"]=="EXAMPLE AS"
    assert brief["verified_takeaway_count"]>=1
    assert all(x.get("source_url") and x.get("retrieved_at") for x in brief["verified_takeaways"])
    assert all("open jobs" not in x["text"].casefold() for x in brief["verified_takeaways"])
    assert any(x["topic"]=="normalized annual accounts" for x in brief["evidence_gaps"])
    assert brief["change_assessment"]["status"]=="no_previous_snapshot"


def test_source_missing_facts_are_not_reframed_as_synthesis_certainty():
    row={"organisation_number":"999999991","name":"EXAMPLE AS",
        "evidence":{"registry":{"status":"source_error"},"website":{"status":"not_found"},
                    "public_activity":{"status":"not_found"}}}
    attach_synthesis(row)
    brief=row["synthesis"]["decision_brief"]
    assert brief["verified_takeaway_count"]==0
    assert not brief["verified_takeaways"]
    assert "unknown" in brief["interpretation_policy"].lower()
