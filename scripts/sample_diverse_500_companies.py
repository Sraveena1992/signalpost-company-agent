#!/usr/bin/env python3
"""500-company public registry sample spread across the Norwegian national universe.

Not the secret Builderr sample. Distinct from a page-0 alphabetical holdout.
"""
import concurrent.futures as cf
import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path

BASE="https://data.brreg.no/enhetsregisteret/api/enheter"
DIRECTORY=Path("artifacts/diverse-500")
SAMPLE_PAGES=100
PER_PAGE=5
SEED="signalpost-cross-universe-norwegian-500-20261114"

def fetch(page):
    url=f"{BASE}?size=1000&page={page}"
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"SignalpostDiversePublicHoldout/1.0"})
    error=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=35) as r:
                data=json.load(r)
            return page,data
        except Exception as exc:
            error=exc
    raise RuntimeError(f"Public registry page {page} failed: {error}")

def main():
    first=fetch(0)[1]
    pages=int((first.get("page") or {}).get("totalPages") or 0)
    if pages<SAMPLE_PAGES:
        raise RuntimeError(f"Not enough registry pages for 100 distributed groups: {pages}")
    # Midpoint of each uniform bin avoids a page-0 alphabetical-only sample.
    indexes=sorted(set(min(pages-1,int((i+0.5)*pages/SAMPLE_PAGES)) for i in range(SAMPLE_PAGES)))
    assert len(indexes)==SAMPLE_PAGES
    result={0:first}
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for page,data in pool.map(fetch,indexes):
            result[page]=data
    selected=[]
    for page in indexes:
        values=(result[page].get("_embedded") or {}).get("enheter") or []
        valid=[{"organisation_number":str(item.get("organisasjonsnummer") or ""),
                "name":item.get("navn"),"legal_form":((item.get("organisasjonsform") or {}).get("kode")),
                "page":page} for item in values]
        valid=[row for row in valid if re.fullmatch(r"\d{9}",row["organisation_number"]) and row["name"]]
        valid.sort(key=lambda row:hashlib.sha256((SEED+"|"+row["organisation_number"]).encode()).hexdigest())
        if len(valid)<PER_PAGE:raise RuntimeError(f"Too few valid companies on page {page}")
        selected.extend(valid[:PER_PAGE])
    orgs=[x["organisation_number"] for x in selected]
    if len(orgs)!=500 or len(set(orgs))!=500:raise RuntimeError("Invalid diverse holdout count or duplicates")
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    (DIRECTORY/"input-500.json").write_text(json.dumps(orgs,ensure_ascii=False,indent=2)+"\n")
    (DIRECTORY/"reference-500.json").write_text(json.dumps({
        "selection":"100 evenly spread public registry pages x 5 deterministic company names",
        "not_Builderr_hidden":True,"page_count":pages,"selected_pages":indexes,"count":500,
        "records":selected,
    },ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"total_pages":pages,"sampled_pages":len(indexes),"companies":len(orgs),
                      "first_page":indexes[0],"last_page":indexes[-1],
                      "first_company":selected[0]["name"],"last_company":selected[-1]["name"]},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
