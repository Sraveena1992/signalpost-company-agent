#!/usr/bin/env python3
"""Adjudication aid: original archived registry evidence vs fresh official source.

This detects source change, NOT whether an old timestamped claim was false.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen, Request

ORG="932850753"
SRC=f"https://data.brreg.no/enhetsregisteret/api/enheter/{ORG}"


def source_values(data):
    addr=data.get("forretningsadresse") or {}
    lines=addr.get("adresse") or []
    if not isinstance(lines,list): lines=[lines]
    addr_text=", ".join(str(x) for x in [*lines,addr.get("postnummer"),addr.get("poststed"),addr.get("kommune"),addr.get("land")] if x not in (None,""))
    return {"Bankruptcy flag":data.get("konkurs"),"Liquidation flag":data.get("underAvvikling"),
            "Registered business address":addr_text}


def run(profile):
    assert str(profile["organisation_number"])==ORG
    ev=(profile.get("evidence") or {}).get("registry_live") or {}
    assert ev.get("source_url")==SRC
    archived={f["claim"]:f["value"] for f in profile.get("synthesis",{}).get("facts",[])
              if f.get("claim") in ("Bankruptcy flag","Liquidation flag","Registered business address")}
    if len(archived)!=3:
        raise ValueError("Target's three archived facts are incomplete")
    now=datetime.now(timezone.utc).isoformat()
    result={"organisation_number":ORG,"official_source_url":SRC,
            "archived_retrieved_at":ev.get("retrieved_at"),
            "archived_source_sha256":ev.get("content_sha256"),
            "archived_claims":archived,"fresh_retrieved_at":now,
            "interpretation":"Fresh differences are temporal discrepancies; adjudicate original captured source separately.",
            "gold_label":None}
    request=Request(SRC,headers={"User-Agent":"SignalpostSourceAudit/1.0 (evidence-audit)","Accept":"application/json"})
    try:
        with urlopen(request,timeout=20) as response:
            raw=response.read(2_000_001)
            result["http_status"]=response.status
        if len(raw)>2_000_000:raise ValueError("Source larger than expected")
        data=json.loads(raw)
        if str(data.get("organisasjonsnummer"))!=ORG:
            raise ValueError("Official source returned a different company")
        current=source_values(data)
        result.update({"fresh_source_sha256":hashlib.sha256(raw).hexdigest(),
                       "fresh_claims":current,
                       "comparisons":{label:{"archived":value,"fresh":current[label],
                                           "same":value==current[label]} for label,value in archived.items()},
                       "status":"fresh_identity_approved"})
    except Exception as exc:
        result.update({"status":"source_unavailable","error_type":type(exc).__name__})
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profiles",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    rows=(json.loads(line) for line in a.profiles.read_text(encoding="utf-8").splitlines() if line.strip())
    matches=[r for r in rows if str(r.get("organisation_number"))==ORG]
    if len(matches)!=1:raise ValueError("Target not found uniquely in archived 500")
    result=run(matches[0])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
