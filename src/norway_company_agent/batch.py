from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .evidence import evidence, utc_now
from .official import accounting_obligation_assessment
from .sampling import iter_bulk


# These are the six public terminal states specified by Builderr. Internal
# fetch outcomes must be mapped to this contract before an envelope is emitted.
TERMINAL_STATES = {
    "available",
    "not_available",
    "blocked",
    "not_applicable",
    "ambiguous",
    "failed",
}

INTERNAL_STATE_MAP = {
    "complete": "available",
    "available": "available",
    "not_found": "not_available",
    "not_available": "not_available",
    "not_applicable": "not_applicable",
    "blocked_policy": "blocked",
    "blocked_robots": "blocked",
    "blocked": "blocked",
    "ambiguous": "ambiguous",
    "source_error": "failed",
    "budget_exhausted": "failed",
    "submission_error": "failed",
    "failed": "failed",
    "not_fetched": "failed",
}


def read_organisation_inputs(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    values: list[Any]
    if source.suffix == ".json":
        body = __import__("json").loads(text)
        values = body if isinstance(body, list) else body.get("organisation_numbers", [])
    elif source.suffix == ".jsonl":
        import json
        values = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        values = [line.strip() for line in text.splitlines() if line.strip()]
    records = []
    for value in values:
        org = value.get("organisation_number") if isinstance(value, dict) else value
        org = "".join(character for character in str(org or "") if character.isdigit())
        if len(org) != 9:
            raise ValueError(f"Invalid Norwegian organisation number: {value!r}")
        record = {"organisation_number": org}
        if isinstance(value, dict):
            for key in ("evaluation_split", "sample_slice"):
                if value.get(key) is not None:
                    record[key] = value[key]
        records.append(record)
    orgs = [record["organisation_number"] for record in records]
    if len(orgs) != len(set(orgs)):
        raise ValueError("Organisation-number input contains duplicates")
    return records


def read_organisation_numbers(path: str | Path) -> list[str]:
    return [record["organisation_number"] for record in read_organisation_inputs(path)]


def profiles_from_bulk(path: str | Path, organisation_numbers: Iterable[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested = list(organisation_numbers)
    wanted = set(requested)
    snapshot_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    retrieved_at = utc_now()
    found: dict[str, dict[str, Any]] = {}
    scanned = 0
    for profile in iter_bulk(path):
        scanned += 1
        org = profile["organisation_number"]
        if org not in wanted:
            continue
        raw = profile.pop("raw", {})
        profile["evidence"] = {
            "registry": evidence(
                "registry", "available", "official_registry_bulk",
                "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                value=raw, retrieved_at=retrieved_at,
                content_sha256=snapshot_sha256, source_row_key=org,
            ),
            "accounting_obligation": accounting_obligation_assessment(profile),
        }
        found[org] = profile
        if len(found) == len(wanted):
            break
    missing = [org for org in requested if org not in found]
    # A frozen snapshot can lag or omit a newly supplied identifier. Keep that
    # company in the batch and let the live official-registry module resolve it;
    # do not abort the entire run or silently drop the input.
    for org in missing:
        found[org] = {"organisation_number": org, "evidence": {}}
    return [found[org] for org in requested], {
        "registry_snapshot_sha256": snapshot_sha256,
        "registry_rows_scanned": scanned,
        "requested": len(requested),
        "selected_from_snapshot": len(requested) - len(missing),
        "missing_from_snapshot": missing,
    }


def evidence_terminal_state(record: dict[str, Any] | None) -> str:
    if not record:
        return "failed"
    return INTERNAL_STATE_MAP.get(str(record.get("status") or ""), "failed")


def _has_substantive_value(value: Any) -> bool:
    """Ignore empty containers and transport metadata when judging published facts."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float, bool)):
        return True
    if isinstance(value, list):
        return any(_has_substantive_value(item) for item in value)
    if isinstance(value, dict):
        ignored = {"_links", "links", "retrieved_at", "source_url", "status", "note", "content_sha256"}
        return any(_has_substantive_value(item) for key, item in value.items() if key not in ignored)
    return False


def entity_terminal_state(profile: dict[str, Any], modules: Iterable[str]) -> str:
    records = profile.get("evidence", {})
    requested = list(modules)

    # Without the official registry identity, later facts cannot be safely
    # attributed to this company. Do not publish guessed identity matches.
    registry = records.get("registry_live") or records.get("registry")
    if not registry:
        return "failed"
    registry_status = registry.get("status")
    if registry_status in {"source_error", "not_fetched"}:
        return "failed"
    if registry_status == "not_found":
        return "not_available"
    if registry_status == "blocked":
        return "blocked"

    substantive_modules = {
        "financials", "financial_history", "roles", "group", "locations",
        "website", "jobs", "public_activity", "news", "reviews", "social",
    }
    for module in requested:
        record = records.get(module)
        if module in substantive_modules and record and record.get("status") == "available" and _has_substantive_value(record.get("value")):
            return "available"

    if any(records.get(module, {}).get("status") == "ambiguous" for module in requested if records.get(module)):
        return "ambiguous"
    if any(records.get(module, {}).get("status") == "blocked" for module in requested if records.get(module)):
        return "blocked"
    if any(records.get(module, {}).get("status") in {"source_error", "not_fetched"} for module in requested if records.get(module)):
        return "failed"
    if any(module not in records for module in requested):
        return "failed"
    return "not_available"


def terminal_envelope(
    profile: dict[str, Any],
    *,
    run_id: str,
    modules: Iterable[str],
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    requested_modules = list(modules)
    module_states = {}
    for module in requested_modules:
        record = profile.get("evidence", {}).get(module)
        module_states[module] = {
            "state": evidence_terminal_state(record),
            "retry_count": int((record or {}).get("retry_count") or 0),
            "final_timestamp": (record or {}).get("retrieved_at") or completed_at,
        }
    return {
        "run_id": run_id,
        "organisation_number": str(profile.get("organisation_number") or ""),
        "state": entity_terminal_state(profile, requested_modules),
        "started_at": started_at,
        "completed_at": completed_at,
        "modules": module_states,
        "profile": profile,
    }


def validate_envelopes(
    envelopes: list[dict[str, Any]],
    expected_count: int,
    expected_organisation_numbers: Iterable[str] | None = None,
) -> dict[str, Any]:
    orgs = [str(item.get("organisation_number") or "") for item in envelopes]
    expected_orgs = [str(org) for org in expected_organisation_numbers] if expected_organisation_numbers is not None else None
    expected_set = set(expected_orgs) if expected_orgs is not None else None
    actual_set = set(orgs)
    missing_organisations = sorted(expected_set - actual_set) if expected_set is not None else []
    unexpected_organisations = sorted(actual_set - expected_set) if expected_set is not None else []
    invalid_entity_states = [
        {"organisation_number": item.get("organisation_number"), "state": item.get("state")}
        for item in envelopes if item.get("state") not in TERMINAL_STATES
    ]
    invalid_module_states = [
        {"organisation_number": item.get("organisation_number"), "module": module, "state": state.get("state") if isinstance(state, dict) else None}
        for item in envelopes
        for module, state in (item.get("modules") or {}).items()
        if not isinstance(state, dict) or state.get("state") not in TERMINAL_STATES
    ]
    invalid_evidence_provenance = []
    for item in envelopes:
        profile = item.get("profile") or {}
        for module, record in (profile.get("evidence") or {}).items():
            if not isinstance(record, dict) or record.get("status") != "available":
                continue
            if not record.get("source_url") or not record.get("retrieved_at"):
                invalid_evidence_provenance.append({
                    "organisation_number": item.get("organisation_number"),
                    "module": module,
                    "missing": [key for key in ("source_url", "retrieved_at") if not record.get(key)] if isinstance(record, dict) else ["record"],
                })
    checks = {
        "exact_expected_count": len(envelopes) == expected_count,
        "unique_organisation_numbers": len(orgs) == len(set(orgs)),
        "exact_organisation_membership": (
            expected_set is None or (
                len(expected_orgs) == len(expected_set) and actual_set == expected_set
            )
        ),
        "all_entity_states_contract_valid": not invalid_entity_states,
        "all_module_states_contract_valid": not invalid_module_states,
        "available_evidence_has_source_and_retrieval_date": not invalid_evidence_provenance,
        "one_envelope_per_input": len(envelopes) == expected_count and len(orgs) == len(set(orgs)),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "invalid_entity_states": invalid_entity_states,
        "invalid_module_states": invalid_module_states,
        "invalid_evidence_provenance": invalid_evidence_provenance,
        "missing_organisations": missing_organisations,
        "unexpected_organisations": unexpected_organisations,
    }


def profile_complete_for_modules(profile: dict[str, Any], modules: Iterable[str]) -> bool:
    records = profile.get("evidence", {})
    return all(module in records and records[module].get("status") != "not_fetched" for module in modules)
