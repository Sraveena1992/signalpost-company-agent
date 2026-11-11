"""Regression cases for selecting the right annual account in financial screening."""
from norway_company_agent.research import _latest_financial, answer_profile, screen_companies


def _row(records, status="available"):
    return {
        "organisation_number": "923609016",
        "name": "EXAMPLE ASA",
        "evidence": {
            "financials": {
                "status": status,
                "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/923609016",
                "retrieved_at": "2026-11-11T00:00:00Z",
                "value": {"records": records},
            }
        },
    }


def test_financial_selection_is_dated_not_first_array_entry():
    row = _row([
        {"period": {"tilDato": "2023-12-31"}, "account_type": "SELSKAP", "revenue": 10},
        {"period": {"tilDato": "2025-12-31"}, "account_type": "SELSKAP", "revenue": 25},
        {"period": {"tilDato": "2024-12-31"}, "account_type": "SELSKAP", "revenue": 20},
    ])
    assert _latest_financial(row)["revenue"] == 25
    facts = answer_profile(row, "What is the revenue?")["facts"]
    assert any(item["claim"] == "Revenue" and item["value"] == 25 for item in facts)


def test_same_period_standalone_preferred_over_group():
    row = _row([
        {"period": {"tilDato": "2025-12-31"}, "account_type": "KONSERN", "revenue": 900},
        {"period": {"tilDato": "2025-12-31"}, "account_type": "SELSKAP", "revenue": 30},
    ])
    assert _latest_financial(row)["revenue"] == 30


def test_latest_reporting_period_wins_over_older_standalone():
    row = _row([
        {"period": {"tilDato": "2025-12-31"}, "account_type": "KONSERN", "revenue": 90},
        {"period": {"tilDato": "2024-12-31"}, "account_type": "SELSKAP", "revenue": 30},
    ])
    assert _latest_financial(row)["revenue"] == 90


def test_unavailable_financial_record_cannot_be_used_for_screening():
    row = _row([{"period": {"tilDato": "2025-12-31"}, "revenue": 100}], status="failed")
    assert _latest_financial(row) == {}


def test_empty_and_undated_records_are_handled():
    assert _latest_financial(_row([])) == {}
    assert _latest_financial(_row([{"revenue": 2}]))["revenue"] == 2
