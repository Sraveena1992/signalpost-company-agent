"""Additional recall only from source-backed official company records."""
from norway_company_agent.research import answer_profile


def test_official_copy_years_are_provenanced_and_not_financial_amounts():
    source = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/987654321/aar"
    p = {"organisation_number": "987654321", "evidence": {
        "financial_history": {"status": "available", "source_url": source,
            "retrieved_at": "2026-11-17T00:00:00Z",
            "value": {"years": ["2023", "2024", "2024", "garbage"]}}
    }}
    facts = [x for x in answer_profile(p, "financial")["facts"]
             if x["claim"] == "Annual accounts copy listed for year"]
    assert [x["value"] for x in facts] == ["2024", "2023"]
    assert all(x["source_url"] == source for x in facts)
    assert not any(x["claim"] == "Revenue" for x in answer_profile(p, "financial")["facts"])


def test_all_distinct_active_official_roles_without_duplicate_claims():
    p = {"organisation_number": "987654321", "evidence": {"roles": {
        "status": "available", "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/987654321/roller",
        "retrieved_at": "2026-11-17T00:00:00Z",
        "value": {"roles": [{"role": "Director", "name": f"Person {i}"} for i in range(20)]
                  + [{"role": "Director", "name": "Person 0"},
                     {"role": "Director", "name": "Inactive", "inactive": True}]}
    }}}
    facts = [x for x in answer_profile(p, "roles")["facts"] if x["classification"] == "official_role_record"]
    assert len(facts) == 20
    assert "Inactive" not in [x["value"] for x in facts]


def test_registered_subunits_must_have_unique_exact_org():
    p = {"organisation_number": "987654321", "evidence": {"locations": {
        "status": "available", "source_url": "https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet=987654321",
        "retrieved_at": "2026-11-17T00:00:00Z",
        "value": {"locations": [{"organisation_number": f"{i:09d}", "name": f"Branch {i}"} for i in range(20)]
                  + [{"organisation_number": "000000000", "name": "Duplicate"},
                     {"organisation_number": "invalid", "name": "Wrong"}]}
    }}}
    facts = [x for x in answer_profile(p, "locations")["facts"] if x["classification"] == "official_subunit_record"]
    assert len(facts) == 20
    assert all(len(x["value"]["organisation_number"]) == 9 for x in facts)
