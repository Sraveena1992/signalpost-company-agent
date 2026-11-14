#!/usr/bin/env python3
"""Truthful all-module batch coverage and source-attribution diagnostics.

This is NOT an independent all-claim gold-label precision score.
"""
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qs

MODULES=["registry","accounting_obligation","registry_live","financials",
         "financial_history","roles","group","locations","website","public_activity"]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--profiles",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    profiles=[json.loads(line) for line in args.profiles.read_text(encoding="utf-8").splitlines() if line.strip()]
    batch=json.loads(args.report.read_text(encoding="utf-8"))
    assert len(profiles)==500, f"Expected 500 profiles, got {len(profiles)}"
    ids=[str(p.get("organisation_number") or "") for p in profiles]
    assert len(set(ids))==500, "Duplicate organisations"
    assert (batch.get("validation") or {}).get("passed") is True, "Batch output contract failure"
    states=defaultdict(Counter)
    missing_source=[]
    source_identity_mismatches=[]
    claim_count=0
    source_linked_claim_count=0
    unsupported_count=0
    news_count=0
    jobs_count=0
    for profile in profiles:
        org=str(profile.get("organisation_number") or "")
        ev=profile.get("evidence") or {}
        for module in MODULES:
            item=ev.get(module) or {}
            status=str(item.get("status") or item.get("state") or "missing")
            states[module][status]+=1
            if status=="available":
                if not item.get("source_url") or not item.get("retrieved_at"):
                    missing_source.append({"organisation":org,"module":module})
                if module in {"registry","registry_live","financials","financial_history","roles","group","locations"}:
                    url=str(item.get("source_url") or "")
                    host=urlparse(url).hostname or ""
                    if host and host not in {"data.brreg.no","data.brreg.no."}:
                        source_identity_mismatches.append({"organisation":org,"module":module,"reason":"not_official_host","url":url})
                    # Brreg detail URLs embed the organisation in the path;
                    # subsidiary /locations lookup uses ?overordnetEnhet=<org>.
                    parsed=urlparse(url)
                    query=parse_qs(parsed.query)
                    in_path=(org in parsed.path)
                    in_parent_query=(module=="locations" and query.get("overordnetEnhet")==[org])
                    if parsed.path.strip("/") and not (in_path or in_parent_query):
                        source_identity_mismatches.append({"organisation":org,"module":module,"reason":"wrong_org_in_source_url","url":url})
        sy=profile.get("synthesis") or {}
        unsupported_count+=len(sy.get("unsupported_or_uncertain") or [])
        for fact in sy.get("facts") or []:
            claim_count+=1
            if fact.get("source_url") and fact.get("retrieved_at"):
                source_linked_claim_count+=1
            else:
                missing_source.append({"organisation":org,"fact":str(fact.get("claim") or "")[:120]})
            cl=str(fact.get("classification") or "")
            news_count+=cl=="verified_company_site_news"
            jobs_count+=cl=="verified_company_site_job_posting"
    result={
        "scope":"500 fresh, full default 10-module runs against public registry identities",
        "not_an_official_score":True,
        "not_a_gold_label_precision_measure":True,
        "companies":len(profiles),
        "batch_contract_pass":True,
        "module_status_counts":{k:dict(states[k]) for k in MODULES},
        "module_available_rates":{k:round(states[k]["available"]/len(profiles),4) for k in MODULES},
        "synthesis_claims":claim_count,
        "synthesis_claims_with_source_and_timestamp":source_linked_claim_count,
        "synthesis_unsupported_or_uncertain":unsupported_count,
        "verified_company_site_news_claims":news_count,
        "verified_company_site_job_claims":jobs_count,
        "source_metadata_gaps":missing_source[:100],
        "official_source_attribution_issues":source_identity_mismatches[:100],
        "notes":[
           "This report measures availability and structural provenance, not factual accuracy against independently adjudicated claim labels.",
           "Unavailable modules count as unavailable; no coverage inflation.",
           "News/jobs require exact-company source provenance before inclusion.",
           "Builderr's private company set and rubric scores are not accessible to this public benchmark."
        ]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert not missing_source, "Missing evidence source metadata; inspect report"
    assert not source_identity_mismatches, "Wrong attribution evidence source detected; inspect report"

if __name__=="__main__":main()
