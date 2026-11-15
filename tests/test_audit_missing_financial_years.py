"""Official year-over-year comparison must separate absent years and mismatch."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from verify_all_claims_live import compare_finance


def account(year,revenue):
    return {"regnskapsperiode":{"tilDato":f"{year}-12-31"},
            "regnskapstype":"SELSKAP","valuta":"NOK",
            "resultatregnskapResultat":{"driftsresultat":{"driftsinntekter":{"sumDriftsinntekter":revenue}}}}


def expected():
    return {"current_year":"2025","previous_year":"2024",
            "account_type":"SELSKAP","currency":"NOK",
            "previous_revenue":100,"absolute_change":20,"percentage_change":20.0}


def test_missing_live_comparison_year_unverifiable_not_false():
    assert compare_finance("Revenue year-over-year change",expected(),[account(2025,120)]) is None
    assert compare_finance("Revenue year-over-year change",expected(),[account(2024,100)]) is None


def test_source_matches_actual_two_years():
    assert compare_finance("Revenue year-over-year change",expected(),
                           [account(2025,120),account(2024,100)]) is True


def test_real_revenue_disagreement_remains_false():
    assert compare_finance("Revenue year-over-year change",expected(),
                           [account(2025,140),account(2024,100)]) is False
