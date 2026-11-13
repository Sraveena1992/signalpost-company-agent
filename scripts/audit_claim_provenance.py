#!/usr/bin/env python3
"""Audit claim-to-company provenance for a saved JSONL profile batch.

This is a deterministic source-integrity audit, NOT a ground-truth precision score.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REGISTRY_PATH = re.compile(r"/(?:enheter|regnskap)/(\d{9})(?:/|$)")


def audit(path: Path) -> dict:
    counts = Counter()
    flags = []
    orgs = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        profile = json.loads(raw)
        org = str(profile.get("organisation_number") or "")
        name = str(profile.get("name") or "")
        counts["profiles"] += 1
        if not re.fullmatch(r"\d{9}", org) or org in orgs:
            flags.append({"line": lineno, "org": org, "reason": "Invalid or repeated organisation number"})
        orgs.add(org)
        facts = ((profile.get("synthesis") or {}).get("facts") or [])
        counts["claims"] += len(facts)
        for idx, fact in enumerate(facts):
            claim = str(fact.get("claim") or "")
            src = str(fact.get("source_url") or "")
            stamp = fact.get("retrieved_at")
            label = {"line": lineno, "org": org, "claim_index": idx, "claim": claim}
            if not src.startswith(("https://", "http://")) or not stamp:
                flags.append({**label, "reason": "Claim lacks source URL/retrieval timestamp"})
                continue
            counts["source_linked_claims"] += 1
            url = urlparse(src)
            match = REGISTRY_PATH.search(url.path)
            if match and match.group(1) != org:
                flags.append({**label, "reason": "Original-source organisation number mismatch", "source_url": src})
            if url.path.endswith("/underenheter") and "overordnetEnhet" in parse_qs(url.query):
                parents = parse_qs(url.query)["overordnetEnhet"]
                if org not in parents:
                    flags.append({**label, "reason": "Subunit belongs to another organisation", "source_url": src})
            if fact.get("classification") in ("company_linked_social_profile", "company_reported_claim"):
                counts["company_owned_web_claims"] += 1
                website = ((profile.get("evidence") or {}).get("website") or {})
                value = website.get("value") or {}
                if not (value.get("identity_assessment") or {}).get("publishable"):
                    flags.append({**label, "reason": "Company-site claim without explicit identity approval"})
                if fact.get("classification") == "company_linked_social_profile":
                    flags.append({**label, "reason": "Social account ownership requires independent proof; handle match is insufficient"})
        for k, evidence in (profile.get("evidence") or {}).items():
            if evidence.get("status") == "available":
                counts["available_modules"] += 1
                if not evidence.get("source_url") or not evidence.get("retrieved_at"):
                    flags.append({"line": lineno, "org": org, "module": k, "reason": "Available module missing provenance"})
            if k in ("website", "public_activity") and evidence.get("status") == "available":
                counts[k + "_available"] += 1
        unknowns = ((profile.get("synthesis") or {}).get("unknowns") or [])
        counts["explicit_unknowns"] += len(unknowns)
    return {
        "audit_kind": "deterministic_claim_provenance_not_independent_fact_checking",
        "counts": dict(counts),
        "flag_count": len(flags),
        "flags": flags,
        "note": "A clean source URL does not independently prove the source supports a factual claim. A 95% accuracy score requires human or gold-label verification.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-flags", action="store_true")
    args = parser.parse_args()
    report = audit(args.profiles)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if args.fail_on_flags and report["flag_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
