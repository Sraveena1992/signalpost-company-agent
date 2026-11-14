#!/usr/bin/env python3
"""Conservative coverage gate for a specific organisation-number batch.

This script audits claimed source provenance and output structure. It cannot
independently determine factual truth from self-reported verification flags.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

VALID = {"available", "not_available", "blocked", "not_applicable", "ambiguous", "failed"}


def load_ids(path):
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    ids = json.loads(text) if text.startswith("[") else text.splitlines()
    ids = [str(x).strip() for x in ids if str(x).strip()]
    if len(ids) != len(set(ids)) or any(len(x) != 9 or not x.isdecimal() for x in ids):
        raise ValueError("Input IDs must be distinct 9-digit organisation numbers")
    return ids


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def valid_source(observation):
    url = urlparse(str(observation.get("source_url") or ""))
    return url.scheme in ("http", "https") and bool(url.hostname) and bool(
        observation.get("retrieved_at") and str(observation.get("evidence_span") or "").strip()
    )


def evaluate(ids, rows):
    expected = set(ids)
    seen = {}
    errors = []
    states = Counter()
    source_complete = 0
    independently_marked = 0
    candidates = 0
    for row in rows:
        org = str(row.get("organisation_number") or "")
        if org not in expected:
            errors.append("Unexpected company: " + org)
            continue
        if org in seen:
            errors.append("Duplicate company: " + org)
            continue
        seen[org] = row
        status = row.get("status")
        states[str(status)] += 1
        if status not in VALID:
            errors.append("Invalid status: " + org)
        observations = row.get("observations") or []
        if not isinstance(observations, list):
            errors.append("Invalid observations: " + org)
            continue
        if observations and status != "available":
            errors.append("Claim with nonavailable status: " + org)
        for item in observations:
            candidates += 1
            if not isinstance(item, dict) or str(item.get("organisation_number", org)) != org:
                errors.append("Invalid claim entity: " + org)
                continue
            if not valid_source(item):
                errors.append("Missing claim provenance: " + org)
                continue
            source_complete += 1
            if item.get("independently_verified") is True and item.get("original_source_checked") is True:
                independently_marked += 1
    missing = sorted(expected - set(seen))
    checked = sum(row.get("checked") is True for row in seen.values())
    return {
        "input_rows": len(rows),
        "expected_companies": len(ids),
        "unique_expected_companies": len(seen),
        "companies_with_completed_check": checked,
        "coverage_percent": round(100 * checked / len(ids), 2) if ids else None,
        "candidate_observations": candidates,
        "source_provenance_complete_candidates": source_complete,
        "self_reported_independently_checked_candidates_not_gold_validated": independently_marked,
        "status_counts": dict(states),
        "missing_company_count": len(missing),
        "first_missing_companies": missing[:30],
        "errors": errors[:100],
        "structural_pass": not missing and not errors and checked == len(ids),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--organisations", required=True)
    parser.add_argument("--news", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--expected-count", type=int, default=500)
    args = parser.parse_args()
    ids = load_ids(args.organisations)
    if len(ids) != args.expected_count:
        raise SystemExit(f"Expected {args.expected_count} companies, found {len(ids)}")
    report = {
        "expected_companies": len(ids),
        "news": evaluate(ids, load_jsonl(args.news)),
        "jobs": evaluate(ids, load_jsonl(args.jobs)),
        "independent_95_percent_accuracy_established": False,
        "caution": "Structural/provenance checks are NOT independent truth labels, recall evidence, or an official competition score.",
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not (report["news"]["structural_pass"] and report["jobs"]["structural_pass"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
