#!/usr/bin/env python3
"""Independent re-fetch public holdout for exact legal identity; NOT hidden Builderr labels.

The reference names and legal forms are extracted from a public Norwegian registry
search snapshot before invoking the agent. Validated dimensions: 9-digit legal
identity, official name, organisation form, cited record. Not financial/news/jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

URL="https://data.brreg.no/enhetsregisteret/api/enheter?size=1000&page=0"
N=500


def norm(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def prepare(directory):
    req=urllib.request.Request(URL,headers={
        "Accept":"application/vnd.brreg.enhetsregisteret.enhet.v2+json, application/json;q=0.9",
        "User-Agent":"SignalpostIndependentPublicIdentityHoldout/1.0"})
    with urllib.request.urlopen(req,timeout=90) as response:
        body=json.load(response)
    values=((body.get("_embedded") or {}).get("enheter") or [])
    records={}
    for row in values:
        org=str(row.get("organisasjonsnummer") or "")
        if not re.fullmatch(r"[0-9]{9}",org) or not row.get("navn"):continue
        records[org]={
            "organisation_number":org,"name":row["navn"],
            "legal_form":((row.get("organisasjonsform") or {}).get("kode")),
        }
    if len(records)<N:
        raise RuntimeError(f"Insufficient public identities for holdout: {len(records)}; refusing to invent data")
    selected=sorted(records.values(),key=lambda x:hashlib.sha256(
        ("signalpost-public-holdout-20261113|"+x["organisation_number"]).encode()).hexdigest())[:N]
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"reference-identity-500.json").write_text(
        json.dumps({"source":URL,"reference_scope":"public registry snapshot only",
                    "count":N,"records":selected},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (directory/"input-500.json").write_text(
        json.dumps([x["organisation_number"] for x in selected],indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"selected":len(selected),"source":URL},indent=2))


def score(directory):
    ref=json.loads((directory/"reference-identity-500.json").read_text(encoding="utf-8"))
    expected={r["organisation_number"]:r for r in ref["records"]}
    rows=[json.loads(line) for line in (directory/"profiles-500.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    report=json.loads((directory/"run-report-500.json").read_text(encoding="utf-8"))
    seen={}
    for row in rows:
        org=str(row.get("organisation_number") or "")
        if org in seen:raise AssertionError("Duplicate generated company "+org)
        seen[org]=row
    if set(seen)!=set(expected):
        raise AssertionError(f"500 holdout membership invalid. Missing={len(set(expected)-set(seen))}; extra={len(set(seen)-set(expected))}")
    outcomes={"matched":0,"mismatched":0,"unavailable":0}
    failures=[]
    for org,reference in expected.items():
        row=seen[org]
        record=(row.get("evidence") or {}).get("registry_live") or {}
        if record.get("status")!="available":
            outcomes["unavailable"]+=1
            failures.append({"org":org,"reason":"official_registry_unavailable","status":record.get("status")})
            continue
        source_url=record.get("source_url") or ""
        source_path=urlparse(source_url).path.rstrip("/")
        name=norm(row.get("name"))
        label=norm(reference.get("name"))
        official_org=str((record.get("value") or {}).get("organisation_number") or "")
        observed_form=norm(row.get("legal_form"))
        expected_form=norm(reference.get("legal_form"))
        ok=(name==label and official_org==org and source_path.endswith("/"+org)
            and (not expected_form or observed_form==expected_form))
        if ok:outcomes["matched"]+=1
        else:
            outcomes["mismatched"]+=1
            failures.append({"org":org,"reason":"wrong_company_or_reference_changed",
                "expected_name":reference["name"],"observed_name":row.get("name"),
                "expected_legal_form":reference.get("legal_form"),"observed_legal_form":row.get("legal_form"),
                "source_url":source_url,"value_org":official_org})
    accuracy=outcomes["matched"]/N
    coverage=(outcomes["matched"]+outcomes["mismatched"])/N
    result={"benchmark":"public-500-official-identity-holdout",
            "independent":False,
            "reference":"official registry search snapshot; same original data authority as agent",
            "limitations":"Does not measure official Builderr hidden 500, all-field factual precision, news, jobs or synthesis rubric.",
            "count":N,"outcomes":outcomes,
            "exact_identity_match_rate":round(accuracy,5),
            "registry_response_coverage":round(coverage,5),
            "zero_wrong_company":outcomes["mismatched"]==0,
            "at_least_95_percent_identity_match":accuracy>=0.95,
            "batch_contract_passed":bool((report.get("validation") or {}).get("passed")),
            "first_failures":failures[:50]}
    (directory/"public-holdout-500-report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if outcomes["mismatched"] or accuracy<0.95 or not result["batch_contract_passed"]:
        raise SystemExit("Public 500 legal identity holdout failed; inspect report.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["prepare","score"])
    parser.add_argument("--directory",type=Path,default=Path("artifacts/public-500"))
    args=parser.parse_args()
    (prepare if args.command=="prepare" else score)(args.directory)
