#!/usr/bin/env python3
"""Report coverage gaps from completed Signalpost profile JSONL batches.

This is an audit of stored evidence, not an external search or independent validation.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output-dir", default="artifacts/coverage-audit")
    parser.add_argument("--expected-count", type=int, default=500)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    profiles = [json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    ids = [str(p.get("organisation_number") or "") for p in profiles]
    if len(ids) != args.expected_count or len(ids) != len(set(ids)) or any(not value for value in ids):
        raise SystemExit("FAIL: invalid expected count, duplicate company, or missing organisation number")
    counts = Counter()
    rows = []
    for profile in profiles:
        evidence = profile.get("evidence") or {}
        website = evidence.get("website") or {}
        identity = (website.get("value") or {}).get("identity_assessment") or {}
        web_ok = website.get("status") == "available" and identity.get("publishable") is True
        activity = evidence.get("public_activity") or {}
        observations = (activity.get("value") or {}).get("observations") or []
        news = [o for o in observations if o.get("signal_type") == "public_post" and o.get("source_url") and o.get("published_at") and o.get("content_sha256")]
        ext = profile.get("external_observations") or []
        jobs = [o for o in ext if o.get("signal_type") in {"job_posting", "job_listing"} and o.get("source_url") and o.get("retrieved_at") and o.get("exact_entity") is True]
        item = {
            "organisation_number": str(profile["organisation_number"]),
            "name": profile.get("name"),
            "website_verified": web_ok,
            "website_status": website.get("status", "missing"),
            "public_activity_status": activity.get("status", "missing"),
            "news_evidence_candidates": len(news),
            "job_evidence_candidates": len(jobs),
            "needs_website_discovery": not web_ok,
            "needs_news_source_check": not news,
            "needs_job_source_check": not jobs,
        }
        rows.append(item)
        counts["websites_verified"] += int(web_ok)
        counts["companies_with_public_activity"] += int(activity.get("status") == "available")
        counts["news_candidates"] += len(news)
        counts["job_candidates"] += len(jobs)
        counts["companies_with_news_candidates"] += int(bool(news))
        counts["companies_with_job_candidates"] += int(bool(jobs))
    report = {
        "input_companies": len(profiles),
        "counts": dict(counts),
        "caution": "These are evidence candidates, not independent gold-label verification. Zero means no qualifying item in input profiles, not proof of no company news/jobs.",
    }
    (out / "coverage-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "company-coverage.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for label, key in (("websites", "needs_website_discovery"), ("news", "needs_news_source_check"), ("jobs", "needs_job_source_check")):
        (out / f"needs-{label}.jsonl").write_text("".join(json.dumps({"organisation_number": r["organisation_number"], "name": r["name"]}, ensure_ascii=False) + "\n" for r in rows if r[key]), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
