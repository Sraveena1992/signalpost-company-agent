from norway_company_agent.official import normalize_financials
from norway_company_agent.research import answer_profile


def test_financials_are_sorted_by_latest_reporting_period_before_truncation():
    older = {
        "id": "old",
        "regnskapsperiode": {
            "fraDato": "2023-01-01",
            "tilDato": "2023-12-31",
        },
        "resultatregnskapResultat": {
            "driftsresultat": {
                "driftsinntekter": {
                    "sumDriftsinntekter": 100,
                }
            }
        },
    }

    newer = {
        "id": "new",
        "regnskapsperiode": {
            "fraDato": "2025-01-01",
            "tilDato": "2025-12-31",
        },
        "resultatregnskapResultat": {
            "driftsresultat": {
                "driftsinntekter": {
                    "sumDriftsinntekter": 250,
                }
            }
        },
    }

    middle = {
        "id": "middle",
        "regnskapsperiode": {
            "fraDato": "2024-01-01",
            "tilDato": "2024-12-31",
        },
        "resultatregnskapResultat": {
            "driftsresultat": {
                "driftsinntekter": {
                    "sumDriftsinntekter": 180,
                }
            }
        },
    }

    normalized = normalize_financials([older, middle, newer])

    assert [
        record["period"]["tilDato"]
        for record in normalized["records"]
    ] == [
        "2025-12-31",
        "2024-12-31",
        "2023-12-31",
    ]

    assert normalized["records"][0]["revenue"] == 250


def test_synthesis_chooses_latest_dated_financial_record_even_if_input_is_unsorted():
    financials = {
        "status": "available",
        "source_url": (
            "https://data.brreg.no/regnskapsregisteret/"
            "regnskap/123456789"
        ),
        "retrieved_at": "2026-10-23T00:00:00Z",
        "value": {
            "records": [
                {
                    "period": {
                        "fraDato": "2023-01-01",
                        "tilDato": "2023-12-31",
                    },
                    "revenue": 100,
                },
                {
                    "period": {
                        "fraDato": "2025-01-01",
                        "tilDato": "2025-12-31",
                    },
                    "revenue": 250,
                },
            ]
        },
    }

    result = answer_profile(
        {
            "organisation_number": "123456789",
            "evidence": {
                "financials": financials,
            },
        },
        "Give me a company overview",
    )

    period_fact = next(
        fact
        for fact in result["facts"]
        if fact["claim"] == "Reporting period"
    )

    revenue_fact = next(
        fact
        for fact in result["facts"]
        if fact["claim"] == "Revenue"
    )

    assert period_fact["value"]["tilDato"] == "2025-12-31"
    assert revenue_fact["value"] == 250
