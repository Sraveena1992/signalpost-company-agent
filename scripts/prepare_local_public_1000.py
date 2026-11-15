#!/usr/bin/env python3
"""Local 1,000-company public Brønnøysund scale check, NOT a Builderr official run.

The scorer alone supplies its confidential shared company batch.
"""
from __future__ import annotations
import argparse
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

URL="https://data.brreg.no/enhetsregisteret/api/enheter"
def select_public_orgs(count=1000):
    if count != 1000:
        raise ValueError("This check is scoped to exactly 1,000 public companies")
    result=[]
    seen=set()
    for page in range(5):
        query=URL+"?"+urlencode({"size":1000,"page":page})
        req=urllib.request.Request(query,headers={
            "User-Agent":"SignalpostPublicScaleValidator/1.0",
            "Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=90) as response:
            source=json.load(response)
        companies=(source.get("_embedded") or {}).get("enheter") or []
        for row in companies:
            org=str(row.get("organisasjonsnummer") or "")
            if re.fullmatch(r"[0-9]{9}",org) and org not in seen and row.get("navn"):
                seen.add(org)
                result.append(org)
                if len(result)==count:
                    return result
    raise RuntimeError(f"Official public registry returned only {len(result)} distinct companies")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    args=p.parse_args()
    orgs=select_public_orgs()
    for path in (args.output,args.manifest):path.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text("".join(json.dumps({"organisation_number":org})+"\n" for org in orgs))
    args.manifest.write_text(json.dumps({
        "source":URL,"batch_kind":"PUBLIC_NON_OFFICIAL_SCALE_TEST",
        "organisation_count":len(orgs),
        "limit":"Not a Builderr-provided fixed official batch, not a scored evaluation. "
                "Does not imply all companies belong to the eligible financial-filer universe."
    },indent=2)+"\n")
    print(f"Selected exactly {len(orgs)} unique public Norwegian company identifiers")


if __name__=="__main__":
    main()
