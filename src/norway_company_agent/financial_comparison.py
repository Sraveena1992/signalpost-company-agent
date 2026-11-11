"""Evidence-preserving financial comparison for two Norwegian company profiles.

This module does not fetch data or infer values: it consumes already verified
normalized financial records and explicitly flags incomparable accounts.
"""
from __future__ import annotations

from typing import Any

from .research import _latest_financial


def _financial_summary(profile: dict[str, Any]) -> dict[str, Any]:
    financial = (profile.get("evidence") or {}).get("financials") or {}
    latest = _latest_financial(profile)
    period = latest.get("period") or {}
    period_end = period.get("tilDato") if isinstance(period, dict) else None
    scope = str(latest.get("account_type") or "").upper() or None
    currency = latest.get("currency")
    return {
        "organisation_number": str(profile.get("organisation_number") or ""),
        "name": profile.get("name"),
        "status": financial.get("status") or "not_fetched",
        "period_end": period_end,
        "account_type": scope,
        "revenue_scope": latest.get("revenue_scope"),
        "currency": currency,
        "revenue": latest.get("revenue"),
        "operating_result": latest.get("operating_result"),
        "annual_result": latest.get("annual_result"),
        "source_url": financial.get("source_url") if latest else None,
        "retrieved_at": financial.get("retrieved_at") if latest else None,
    }


def compare_financial_profiles(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Return source-linked facts and an explicit comparison eligibility verdict."""
    left, right = _financial_summary(a), _financial_summary(b)
    reasons: list[str] = []
    if not left["organisation_number"] or not right["organisation_number"]:
        reasons.append("missing_identity")
    if left["organisation_number"] == right["organisation_number"]:
        reasons.append("same_company")
    if left["status"] != "available" or right["status"] != "available":
        reasons.append("financial_data_unavailable")
    if left["revenue"] is None or right["revenue"] is None:
        reasons.append("missing_revenue")
    if not left["period_end"] or left["period_end"] != right["period_end"]:
        reasons.append("reporting_period_mismatch")
    if not left["currency"] or left["currency"] != right["currency"]:
        reasons.append("currency_mismatch")
    if not left["account_type"] or left["account_type"] != right["account_type"]:
        reasons.append("account_scope_mismatch")
    if not left["source_url"] or not right["source_url"]:
        reasons.append("missing_source")

    comparable = not reasons
    # Numeric arithmetic is intentionally omitted: a financial comparison without
    # shared period/currency/scope is misleading. UI can render this verdict.
    return {
        "company_a": left,
        "company_b": right,
        "revenue_comparable": comparable,
        "non_comparable_reasons": reasons,
        "source_policy": "Actual official annual-account fields; no currency conversion, normalization or invented figures.",
    }
