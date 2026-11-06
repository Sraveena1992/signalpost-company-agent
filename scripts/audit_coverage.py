#!/usr/bin/env python3
"""Read-only diagnostic report for Signalpost batch runs.

Does not claim to compute hidden-batch recall or precision.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(report: dict, profiles=None) -> dict:
    validation = report.get("validation") or {}
    result = {
        "run_id": report.get("run_id"),
        "count": {
            "inputs": report.get("input_count"),
            "outputs": report.get("emitted_envelopes"),
            "fetched_this_run": report.get("profiles_fetched_this_run"),
            "resumed": report.get("resumed_profiles"),
        },
        "contract_checks": validation.get("checks") or {},
        "contract_pass": validation.get("passed"),
        "modules_requested": report.get("modules") or [],
        "optional_discovery": report.get("tavily_discovery") or {},
        "operations": report.get("operations") or {},
        "notes": [
            "Contract success does not measure hidden-batch recall or claim precision.",
            "Resumed profiles are not equivalent to profiles freshly retrieved in this run.",
            "A source URL and retrieval timestamp do not prove that the cited source supports each claim.",
        ],
    }
    if profiles is not None:
        rows = list(profiles)
        states = Counter()
        uncertain = 0
        missing = []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            synthesis = row.get("synthesis") or {}
            if isinstance(synthesis, dict):
                uncertain += len(synthesis.get("unsupported_or_uncertain") or [])
            for name, observation in (row.get("evidence") or {}).items():
                if not isinstance(observation, dict):
                    continue
                state = observation.get("state", observation.get("status", "unknown"))
                states[(name, state)] += 1
                if state == "available" and (not observation.get("source_url") or not observation.get("retrieved_at")):
                    missing.append({"row": i, "module": name})
        result["profile_audit"] = {
            "rows": len(rows),
            "module_state_counts": {f"{key[0]}:{key[1]}": count for key, count in sorted(states.items())},
            "unsupported_or_uncertain_items": uncertain,
            "available_evidence_missing_source_or_timestamp": missing[:50],
        }
        result["notes"].append("Module-state frequencies are coverage diagnostics, not gold-label recall or precision.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--profiles", help="Optional evidence-rich profile JSONL")
    parser.add_argument("--out", help="Optional JSON output path; otherwise stdout")
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    profiles = (
        (json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8").splitlines() if line.strip())
        if args.profiles else None
    )
    content = json.dumps(audit(report, profiles), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
