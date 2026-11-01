from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from norway_company_agent.official import normalize_financials
from norway_company_agent.research import answer_profile


def account(year, amount, kind="SELSKAP", currency="NOK"):
    return {
        "id": f"{year}-{kind}",
        "regnskapstype": kind,
        "valuta": currency,
        "regnskapsperiode": {"fraDato": f"{year}-01-01", "tilDato": f"{year}-12-31"},
        "resultatregnskapResultat": {"driftsresultat": {"driftsinntekter": {"sumDriftsinntekter": amount}}},
    }


class FinancialScopeTests(unittest.TestCase):
    def test_comparable_company_revenue(self):
        records = normalize_financials([account(2023, 100), account(2024, 120)])["records"]
        self.assertEqual(records[0]["revenue_scope"], "company (standalone)")
        self.assertEqual(records[0]["revenue_yoy"]["absolute_change"], 20)
        self.assertEqual(records[0]["revenue_yoy"]["percentage_change"], 20.0)

    def test_no_group_company_mixing(self):
        records = normalize_financials([account(2023, 100, "SELSKAP"), account(2024, 150, "KONSERN")])["records"]
        self.assertEqual(records[0]["revenue_scope"], "group (consolidated)")
        self.assertIsNone(records[0]["revenue_yoy"])

    def test_missing_year_does_not_create_change(self):
        records = normalize_financials([account(2022, 100), account(2024, 120)])["records"]
        self.assertIsNone(records[0]["revenue_yoy"])

    def test_zero_prior_revenue_does_not_invent_percent(self):
        records = normalize_financials([account(2023, 0), account(2024, 120)])["records"]
        self.assertIsNone(records[0]["revenue_yoy"]["percentage_change"])

    def test_research_displays_scope_and_yoy(self):
        financial = {"status": "available", "source_url": "https://data.brreg.no/regnskapsregisteret/regnskap/123", "value": normalize_financials([account(2023, 100), account(2024, 120)])}
        result = answer_profile({"organisation_number": "123", "evidence": {"financials": financial}}, "revenue")
        facts = {item["claim"]: item["value"] for item in result["facts"]}
        self.assertEqual(facts["Revenue accounting scope"], "company (standalone)")
        self.assertEqual(facts["Revenue year-over-year change"]["percentage_change"], 20.0)


if __name__ == "__main__":
    unittest.main()
