#!/usr/bin/env python3
"""Independent fresh source re-fetch of archived 500-company SIGNALPOST claims.

Only explicitly matched facts count as confirmed. This is NOT Builderr's private
gold-label benchmark: content may have changed after the original retrieval.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, parse_qs

def getpath(value, *parts):
    for part in parts:
        if not isinstance(value,dict):return None
        value=value.get(part)
    return value

def canon(v):
    return re.sub(r"\s+"," ",str(v or "").strip()).casefold()

def fresh(url):
    host=urlparse(url).hostname or ""
    if not(host=="data.brreg.no" or host.endswith(".speiding.no") or
           host in {"www.speiding.no","speiding.no"}):
        return {"state":"not_rechecked_other_site"}
    try:
        request=urllib.request.Request(url,headers={"User-Agent":"SignalpostIndependentVerifier/1.0 (evidence-audit)","Accept":"application/json,text/html;q=0.8"})
        with urllib.request.urlopen(request,timeout=18) as response:
            raw=response.read(4_000_000)
            if "json" in response.headers.get("Content-Type",""):
                return {"state":"available","body":json.loads(raw)}
            return {"state":"available_html","text":raw.decode("utf-8","replace")[:200000]}
    except Exception as exc:
        return {"state":"unavailable","reason":type(exc).__name__}

def address_raw(value):
    if not isinstance(value,dict):return ""
    lines=value.get("adresse") or []
    if not isinstance(lines,list):lines=[lines]
    return ", ".join(str(x) for x in [*lines,value.get("postnummer"),value.get("poststed"),value.get("kommune"),value.get("land")] if x not in (None,""))

def compare_registry(label,value,body,org):
    if str(body.get("organisasjonsnummer"))!=org:return False
    mapping={
        "Registered name":body.get("navn"),
        "Organisation number":body.get("organisasjonsnummer"),
        "Legal form":getpath(body,"organisasjonsform","kode"),
        "Registry employee count":body.get("antallAnsatte"),
        "Registered industry":getpath(body,"naeringskode1","beskrivelse"),
        "Registered industry code":getpath(body,"naeringskode1","kode"),
        "Bankruptcy flag":body.get("konkurs"),
        "Liquidation flag":body.get("underAvvikling"),
        "Latest reported annual accounts period":body.get("sisteInnsendteAarsregnskap"),
        "Registered business address":address_raw(body.get("forretningsadresse")),
        "Registered postal address":address_raw(body.get("postadresse")),
    }
    if label not in mapping:return None
    return value==mapping[label]

def compare_finance(label,value,body):
    if not isinstance(body,list):return None
    paths={
        "Revenue":("resultatregnskapResultat","driftsresultat","driftsinntekter","sumDriftsinntekter"),
        "Operating result":("resultatregnskapResultat","driftsresultat","driftsresultat"),
        "Annual result":("resultatregnskapResultat","aarsresultat"),
        "Assets":("eiendeler","sumEiendeler"),
        "Debt":("egenkapitalGjeld","gjeldOversikt","sumGjeld"),
        "Reporting period":("regnskapsperiode",),
        "Revenue currency":("valuta",),
    }
    if label in paths:
        return any(getpath(item,*paths[label])==value for item in body)
    if label=="Revenue accounting scope":
        target={"company (standalone)":"SELSKAP","group (consolidated)":"KONSERN"}.get(value)
        if not target:return None
        return any(item.get("regnskapstype")==target for item in body)
    if label=="Revenue year-over-year change":
        if not isinstance(value,dict):return False
        prev=value.get("previous_revenue")
        pct=value.get("percentage_change")
        if prev in (0,None) or not isinstance(pct,(int,float)):return False
        current=prev+value.get("absolute_change",0)
        records={}
        for item in body:
            period=item.get("regnskapsperiode") or {}
            year=str(period.get("tilDato") or "")[:4]
            key=(year,item.get("regnskapstype"),item.get("valuta"))
            revenue=getpath(item,"resultatregnskapResultat","driftsresultat","driftsinntekter","sumDriftsinntekter")
            records.setdefault(key,[]).append(revenue)
        key=(str(value["current_year"]),value.get("account_type"),value.get("currency"))
        old=(str(value["previous_year"]),value.get("account_type"),value.get("currency"))
        return any(r==current for r in records.get(key,[])) and any(r==prev for r in records.get(old,[])) and round((current-prev)/abs(prev)*100,2)==round(pct,2)
    return None

def compare_roles(label,value,body):
    if not isinstance(body,dict):return None
    for group in body.get("rollegrupper") or []:
        for person in group.get("roller") or []:
            typ=getpath(person,"type","beskrivelse") or getpath(group,"type","beskrivelse") or "Registered role"
            names=getpath(person,"person","navn") or {}
            full=" ".join(str(names.get(k) or "") for k in ("fornavn","mellomnavn","etternavn")).strip()
            entity=person.get("enhet") or {}
            entityname=entity.get("navn")
            if isinstance(entityname,list):entityname=" ".join(str(t) for t in entityname)
            display=full or entityname or entity.get("organisasjonsnummer")
            if typ==label and display==value and not person.get("avregistrert"):
                return True
    return False

def compare_subunit(value,body):
    if not isinstance(body,dict) or not isinstance(value,dict):return None
    for item in getpath(body,"_embedded","underenheter") or []:
        if value.get("name")==item.get("navn") and value.get("address")==(
            item.get("beliggenhetsadresse") or item.get("postadresse")):
            return True
    return False

def check_claim(f,org,fetched):
    label=f.get("claim"); value=f.get("value"); kind=f.get("classification")
    src=str(f.get("source_url") or "")
    if not src or not f.get("retrieved_at"):return "contradicted","no source metadata"
    result=fetched.get(src,{"state":"unavailable"})
    if result["state"] not in ("available","available_html"):
        return "unverifiable",result["state"]
    body=result.get("body")
    if kind=="official_registry_fact":
        check=compare_registry(label,value,body,org) if isinstance(body,dict) else None
    elif kind in ("official_annual_account","derived_from_official_annual_accounts"):
        check=compare_finance(label,value,body)
    elif kind=="official_role_record":
        check=compare_roles(label,value,body)
    elif kind=="official_subunit_record":
        check=compare_subunit(value,body)
    elif kind=="verified_company_site_news":
        path=urlparse(src).path
        valid_article=bool(re.search(r"/(?:news|press|aktuelt|nyheter|artikler|blog)/[^/]+",path,re.I))
        date_str=str((value or {}).get("published_at") or "") if isinstance(value,dict) else ""
        valid_date=bool(re.match(r"202[5-6]-",date_str))
        check=False if not valid_article or not valid_date else None
    else:
        check=None  # Website description, social links and jobs need human/HTML assessment.
    if check is True:return "confirmed","fresh original source matches"
    if check is False:return "contradicted","fresh source value differs or unsupported index"
    return "unverifiable","fresh original data insufficient for this claim category"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--profiles",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--workers",type=int,default=10)
    a=p.parse_args()
    rows=[json.loads(x) for x in a.profiles.open() if x.strip()]
    assert len(rows)==500
    all_facts=[(str(row["organisation_number"]),fact) for row in rows for fact in
               (row.get("synthesis") or {}).get("facts") or []]
    urls=sorted({str(f.get("source_url") or "") for _,f in all_facts if f.get("source_url")})
    fetched={}
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(fresh,url):url for url in urls}
        for future in cf.as_completed(futures):
            url=futures[future]
            try:fetched[url]=future.result()
            except Exception as exc:fetched[url]={"state":"unavailable","reason":type(exc).__name__}
    statuses=Counter(); by_category={}
    examples=[]
    for org,f in all_facts:
        state,why=check_claim(f,org,fetched)
        statuses[state]+=1
        kind=str(f.get("classification") or "")
        by_category.setdefault(kind,Counter())[state]+=1
        if state!="confirmed" and len(examples)<150:
            examples.append({"org":org,"claim":f.get("claim"),"classification":kind,
                             "state":state,"reason":why,"url":f.get("source_url")})
    result={
        "scope":"Fresh independently re-fetched source URLs for 500 public-company claim records",
        "NOT_official_Builderr_gold_labels":True,
        "caution":"Source changes, inaccessible endpoints and claims needing human judgment are NOT scored as correct.",
        "companies":len(rows),"claims_total":len(all_facts),"unique_urls":len(urls),
        "urls_status":dict(Counter(item["state"] for item in fetched.values())),
        "claim_status":dict(statuses),
        "confirmation_rate_over_all_claims":round(statuses["confirmed"]/len(all_facts),5),
        "confirmed_fraction_among_decidable":round(statuses["confirmed"]/max(1,statuses["confirmed"]+statuses["contradicted"]),5),
        "category_status":{k:dict(v) for k,v in by_category.items()},
        "examples_not_confirmed":examples,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="examples_not_confirmed"},indent=2))
if __name__=="__main__":main()
