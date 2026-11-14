#!/usr/bin/env python3
"""Deterministic, zero-network jobs evidence funnel from the actual 500-company run.

Uses the archived immutable JSONL profiles, never discovers or invents a job.
Counts unknown/blocked separately from genuinely observed absent candidates.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from urllib.parse import urlparse


def diagnostic(profile):
    org = str(profile["organisation_number"])
    website = (profile.get("evidence") or {}).get("website") or {}
    activity = (profile.get("evidence") or {}).get("public_activity") or {}
    value = website.get("value") or {}
    identity = value.get("identity_assessment") or {}
    pages = value.get("pages") or []
    observations = ((activity.get("value") or {}).get("observations") or [])
    site_verified = website.get("status") == "available" and identity.get("publishable") is True
    ats_keywords = ("greenhouse.io", "lever.co", "teamtailor.com", "webcruiter.no",
                    "webcruiter.com", "jobbnorge.no", "recman.no", "ashbyhq.com",
                    "workable.com", "easycruit.com")
    career_terms = ("job", "careers", "karriere", "stillinger", "stilling", "ledig", "recruit")
    links = sorted({str(url) for p in pages for url in p.get("article_and_job_links") or []
                    if isinstance(url, str) and urlparse(url).scheme in ("https", "http")})
    ats = sorted(x for x in links if any(h in (urlparse(x).hostname or "").casefold() for h in ats_keywords))
    careers = sorted(x for x in links if any(k in (urlparse(x).path or "").casefold() for k in career_terms))
    job_candidates = [(p, job) for p in pages for job in (p.get("job_postings") or []) if isinstance(job, dict)]
    verified = [x for x in observations if isinstance(x, dict) and x.get("signal_type") == "job_posting"
                and str(x.get("organisation_number")) == org and x.get("exact_entity") is True]
    if not site_verified:
        status = "blocked_or_unverified_site" if website.get("status") in ("blocked", "ambiguous") else "unknown_site"
    elif verified:
        status = "verified"
    elif job_candidates:
        status = "structured_candidates_not_accepted"
    elif ats:
        status = "ats_links_not_explored"
    elif careers:
        status = "career_links_no_verified_posting"
    elif pages:
        status = "no_job_candidate_in_bounded_crawl"
    else:
        status = "unknown_unsearched"
    return {
        "organisation_number": org,
        "legal_name": profile.get("name"), "website_status": website.get("status") or "missing",
        "website_url": value.get("final_url") or website.get("source_url"),
        "website_identity_publishable": site_verified,
        "website_identity_reason": identity.get("reasons") or [],
        "website_retrieved_at": website.get("retrieved_at"),
        "website_pages_scanned": len(pages),
        "career_candidate_urls": careers,
        "ats_candidate_urls": ats,
        "jobposting_jsonld_candidates": len(job_candidates),
        "candidate_original_urls": sorted({str(job.get("url") or p.get("url") or "")
                                           for p, job in job_candidates}),
        "verified_site_jobs": len(verified),
        "verified_original_urls": [x.get("source_url") for x in verified],
        "public_activity_status": activity.get("status"),
        "status": status,
        "scope": "Archived bounded site crawl only. 0 candidates does NOT mean no open jobs.",
    }


def run(profiles):
    if len(profiles) != 500:
        raise ValueError(f"Expected exactly 500 audited companies, got {len(profiles)}")
    orgs = [str(p.get("organisation_number") or "") for p in profiles]
    if len(set(orgs)) != 500:
        raise ValueError("500-company input includes duplicate legal organisations")
    rows = [diagnostic(p) for p in profiles]
    return rows, {
        "companies": 500, "diagnostic_scope": "Evidence actually captured by exact archived 500-company run",
        "verified_website_companies": sum(r["website_identity_publishable"] for r in rows),
        "companies_with_career_links": sum(bool(r["career_candidate_urls"]) for r in rows),
        "companies_with_ats_links": sum(bool(r["ats_candidate_urls"]) for r in rows),
        "structured_jobposting_candidates": sum(r["jobposting_jsonld_candidates"] for r in rows),
        "companies_with_verified_jobs": sum(r["verified_site_jobs"] > 0 for r in rows),
        "verified_jobs": sum(r["verified_site_jobs"] for r in rows),
        "status_categories": dict(Counter(r["status"] for r in rows)),
        "claim_boundary": "This offline diagnostic is NOT a new live NAV/ATS search or a proof that jobs do not exist.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profiles", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    profiles = [json.loads(x) for x in args.profiles.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows, summary = run(profiles)
    for path in (args.output, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
