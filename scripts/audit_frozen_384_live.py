#!/usr/bin/env python3
"""Re-fetch original sources for the frozen 384 claim sample, one verdict per case.

This is a source-corroboration AI/algorithm audit, NOT an external human gold
label, not an official Builderr score, and not evidence that every category
was independently adjudicated. Unknowns cannot be silently excluded.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_all_claims_live import fresh, check_claim


def match_frozen(queue, profiles):
    if len(queue) != 384:
        raise ValueError("Frozen blind sample must contain exactly 384 cases")
    if len({str(p["organisation_number"]) for p in profiles}) != 500:
        raise ValueError("Expected exactly 500 archived unique original organisations")
    original = {}
    approved_hosts = set()
    org_hosts = {}
    for profile in profiles:
        org = str(profile["organisation_number"])
        for fact in ((profile.get("synthesis") or {}).get("facts") or []):
            key = json.dumps([org, str(fact.get("classification") or "unclassified"),
                              str(fact.get("claim") or ""),fact.get("value"),
                              fact.get("source_url")],sort_keys=True,ensure_ascii=False,default=str)
            ident = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
            original[ident] = (org, fact)
        site = (profile.get("evidence") or {}).get("website") or {}
        value = site.get("value") or {}
        if site.get("status") == "available" and (value.get("identity_assessment") or {}).get("publishable") is True:
            host = (urlparse(str(value.get("final_url") or site.get("source_url") or "")).hostname or "").casefold()
            if host:
                approved_hosts.add(host)
                org_hosts.setdefault(org, set()).add(host.removeprefix("www."))
    selected=[]
    for q in queue:
        cid=q["claim_id"]
        if cid not in original:raise ValueError(f"Claim missing in immutable original: {cid}")
        org, fact=original[cid]
        if org != str(q["organisation_number"]):raise ValueError("Legal organisation mismatch")
        if str(q.get("claimed_source_url")) != str(fact.get("source_url")):raise ValueError("Claim source mismatch")
        selected.append((q, org, fact))
    if len({q["claim_id"] for q, _, _ in selected}) != 384:
        raise ValueError("Duplicate sample claim IDs")
    return selected, approved_hosts, org_hosts


def audit(queue, profiles, fetch_function=fresh, workers=8):
    selected, hosts, org_hosts = match_frozen(queue, profiles)
    unique_urls = sorted({str(f.get("source_url")) for _,_,f in selected if f.get("source_url")})
    observations={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(fetch_function,url,hosts): url for url in unique_urls}
        for task in as_completed(tasks):
            url=tasks[task]
            try:observations[url]=task.result()
            except Exception as exc:observations[url]={"state":"unavailable","reason":type(exc).__name__}
    checked_at=datetime.now(timezone.utc).isoformat()
    results=[]
    for q,org,f in selected:
        state,reason=check_claim(f,org,observations,org_hosts)
        # Current-time source differences cannot establish an older claim's
        # historical falsity unless original timestamped records also exist.
        reviewer_status={
            "confirmed":"LIVE_SOURCE_MATCH",
            "contradicted":"POTENTIAL_FALSE_REQUIRES_HISTORICAL_REVIEW",
            "unverifiable":"UNVERIFIABLE"
        }[state]
        source=f.get("source_url")
        results.append({
            "claim_id":q["claim_id"],"organisation_number":org,
            "company_name":q.get("company_name"),
            "category":f.get("classification"),"claim":f.get("claim"),
            "claimed_value":f.get("value"),
            "original_source_url":source,
            "archived_source_retrieved_at":f.get("retrieved_at"),
            "fresh_recheck_at":checked_at,
            "source_fetch_state":observations.get(str(source),{}).get("state","not_fetched"),
            "machine_source_verdict":state,"review_status":reviewer_status,
            "reason":reason, "independent_human_gold_label":None,
            "actual_publisher_response_available":observations.get(str(source),{}).get("state") in ("available","available_html"),
        })
    n=Counter(x["machine_source_verdict"] for x in results)
    cat={}
    for x in results:
        cat.setdefault(str(x["category"]),Counter())[x["machine_source_verdict"]]+=1
    summary={
        "scope":"Frozen 384 representative claims, original publisher re-fetch per source URL",
        "observed_at":checked_at, "sample_count":384,
        "unique_source_urls":len(unique_urls),"companies":len({x["organisation_number"] for x in results}),
        "machine_source_verdict_counts":dict(n),
        "category_counts":{k:dict(v) for k,v in cat.items()},
        "conservative_current_corroboration_fraction":round(n["confirmed"]/384,6),
        "machine_precision_among_decidable":round(n["confirmed"]/max(1,n["confirmed"]+n["contradicted"]),6),
        "human_gold_labels":0, "certified_human_95pct":False,
        "independent_ai_gold_label_certified":False,
        "official_builderr_accuracy":None,
        "caution":"Fresh source corroboration, not independent gold truth; unknowns retained, drift may alter historical facts. Do not claim officially certified 95%.",
    }
    return results,summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--queue",type=Path,required=True)
    ap.add_argument("--profiles",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    args=ap.parse_args()
    queue=json.loads(args.queue.read_text(encoding="utf-8"))
    profiles=[json.loads(x) for x in args.profiles.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows,summary=audit(queue,profiles)
    for path in (args.output,args.summary):path.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
