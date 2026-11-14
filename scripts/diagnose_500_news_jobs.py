#!/usr/bin/env python3
"""Diagnose evidence bottlenecks in archived all-module company profiles.

No claims created, no facts relabelled, and no inferred job/news counts.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


def run(path: Path):
    rows=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    result={"companies":len(rows),"website_status":Counter(),
            "public_activity_status":Counter(),"website_identity_gate":Counter(),
            "page_count_total":0,"sites_with_pages":0,"dated_article_candidates":0,
            "jobposting_structured_candidates":0,"news_index_links":0,
            "companies_with_verified_news":0,"companies_with_verified_jobs":0,
            "dated_candidate_details":[],
            "activity_signal_types":Counter(),"sample_rejections":[]}
    for p in rows:
        ev=p.get("evidence") or {}
        w=ev.get("website") or {}
        a=ev.get("public_activity") or {}
        result["website_status"][str(w.get("status") or "missing")]+=1
        result["public_activity_status"][str(a.get("status") or "missing")]+=1
        v=w.get("value") or {}
        identity=(v.get("identity_assessment") or {})
        result["website_identity_gate"]["approved" if identity.get("publishable") is True else "unverified"]+=1
        pages=v.get("pages") or []
        result["page_count_total"]+=len(pages)
        if pages:result["sites_with_pages"]+=1
        for page in pages:
            if page.get("article_like") and page.get("published_at"):
                result["dated_article_candidates"]+=1
                result["dated_candidate_details"].append({"org":str(p.get("organisation_number") or ""),\n                    "name":p.get("name"),"identity_approved":identity.get("publishable") is True,\n                    "url":page.get("url"),"title":page.get("title"),"published_at":page.get("published_at")})
            result["jobposting_structured_candidates"]+=len(page.get("job_postings") or [])
            result["news_index_links"]+=len(page.get("article_and_job_links") or [])
        signals=[x for x in ((a.get("value") or {}).get("observations") or []) if isinstance(x,dict)]
        types={str(x.get("signal_type") or "") for x in signals}
        for x in signals:result["activity_signal_types"][str(x.get("signal_type") or "missing")]+=1
        if "public_post" in types:result["companies_with_verified_news"]+=1
        if "job_posting" in types:result["companies_with_verified_jobs"]+=1
        if pages and len(result["sample_rejections"])<25 and not ("public_post" in types or "job_posting" in types):
            result["sample_rejections"].append({
                "org":str(p.get("organisation_number") or ""),"company":p.get("name"),
                "site":str(w.get("source_url") or "")[:300],
                "approved":identity.get("publishable") is True,
                "pages":len(pages),
                "dated_article_candidates":sum(bool(x.get("article_like") and x.get("published_at")) for x in pages),
                "job_postings":sum(len(x.get("job_postings") or []) for x in pages),
                "possible_reason":"No qualifying dated article or exact employer posting was promoted",
            })
    for key in ("website_status","public_activity_status","website_identity_gate","activity_signal_types"):
        result[key]=dict(result[key])
    result["scope"]="Archived 500-company public batch diagnostic, not independent factual correctness labels"
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--profiles",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=run(args.profiles)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
