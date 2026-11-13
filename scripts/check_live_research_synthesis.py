#!/usr/bin/env python3
"""Verify deployed SIGNALPOST research returns the revised sourced synthesis."""
import json
import time
import urllib.request
from pathlib import Path

BASE="https://signalpost-company-agent.onrender.com"
ORG="923609016"
URL=BASE+"/api/research/"+ORG


def validate():
    req=urllib.request.Request(URL,headers={"Accept":"application/json","User-Agent":"SignalpostVerifiedResearchSmoke/1.0"})
    with urllib.request.urlopen(req,timeout=190) as response:
        assert response.status==200
        data=json.loads(response.read(4_000_000).decode("utf-8"))
    p=data.get("profile") or {}
    assert p.get("organisation_number")==ORG, "Wrong company returned"
    sy=p.get("synthesis") or {}
    facts=sy.get("facts") or []
    approved=[f for f in facts if f.get("classification")=="official_registry_fact"]
    assert any(f.get("claim")=="Registered industry" for f in approved), "New registry synthesis not deployed"
    for fact in approved:
        assert fact.get("source_url") and fact.get("retrieved_at"), "Official fact missing provenance"
        assert ORG in fact["source_url"], "Official fact points to another organisation"
    assert isinstance(sy.get("overview"),list) and isinstance(sy.get("unknowns"),list)
    return {"org":ORG,"verified_registry_claims":len(approved),
            "claims":len(facts),"unknown_topics":len(sy["unknowns"]),
            "source_linked":all(f.get("source_url") and f.get("retrieved_at") for f in facts),
            "result":"PASS","url":URL}


def main():
    error=None
    for attempt in range(2):
        try:
            result=validate()
            Path("artifacts").mkdir(exist_ok=True)
            Path("artifacts/live-research-synthesis-smoke.json").write_text(json.dumps(result,indent=2)+"\n")
            print(json.dumps(result,indent=2),flush=True)
            return
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
            print("Attempt",attempt+1,"failed:",error,flush=True)
            if attempt==0:time.sleep(30)
    raise SystemExit("Live research synthesis not verified: "+str(error))


if __name__=="__main__":
    main()
