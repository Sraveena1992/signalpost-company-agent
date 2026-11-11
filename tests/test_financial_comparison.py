from norway_company_agent.financial_comparison import compare_financial_profiles


def _profile(org, revenue, *, period="2025-12-31", currency="NOK", scope="SELSKAP", status="available", source="https://data.brreg.no/accounts"):
    return {
        "organisation_number": org,
        "name": "TEST AS",
        "evidence": {
            "financials": {
                "status": status,
                "source_url": source,
                "retrieved_at": "2026-11-11",
                "value": {"records": [{"period": {"tilDato": period}, "currency": currency, "account_type": scope, "revenue": revenue}]},
            },
        },
    }


def test_matching_scope_period_and_currency_can_be_compared():
    result = compare_financial_profiles(_profile("111111111", 300), _profile("222222222", 500))
    assert result["revenue_comparable"]
    assert result["company_a"]["revenue"] == 300
    assert result["company_b"]["source_url"]


def test_different_reporting_period_is_not_comparable():
    result = compare_financial_profiles(_profile("111111111", 100), _profile("222222222", 200, period="2024-12-31"))
    assert "reporting_period_mismatch" in result["non_comparable_reasons"]
    assert result["revenue_comparable"] is False


def test_group_accounts_are_not_confused_with_company_accounts():
    result = compare_financial_profiles(_profile("111111111", 100), _profile("222222222", 200, scope="KONSERN"))
    assert "account_scope_mismatch" in result["non_comparable_reasons"]


def test_missing_and_failed_values_are_not_comparable():
    result = compare_financial_profiles(_profile("111111111", None), _profile("222222222", 200, status="failed"))
    assert not result["revenue_comparable"]
    assert "missing_revenue" in result["non_comparable_reasons"]
    assert "financial_data_unavailable" in result["non_comparable_reasons"]


def test_same_company_rejected():
    result = compare_financial_profiles(_profile("111111111", 100), _profile("111111111", 100))
    assert result["non_comparable_reasons"] == ["same_company"]
