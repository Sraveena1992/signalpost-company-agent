#!/usr/bin/env python3
"""Check production Render deployment against the actual new company directory."""
from __future__ import annotations
import argparse
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://signalpost-company-agent.onrender.com"


def read(path, *, timeout=30):
    req=urllib.request.Request(BASE+path,headers={"Accept":"application/json, text/html","User-Agent":"SignalpostDeployAudit/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        if r.status != 200:
            raise RuntimeError(f"{path} returned HTTP {r.status}")
        return r.read(2_000_000).decode("utf-8")


def check():
    health=json.loads(read("/healthz"))
    assert health.get("status") == "ok", health
    home=read("/")
    assert 'id="featured-directory"' in home
    assert 'id="featured-filter"' in home
    assert 'NORWEGIAN COMPANY INTELLIGENCE' in home
    assert 'Explore 300 registry companies' in home
    directory=json.loads(read("/static/verified-directory-300.json"))
    assert len(directory)==300
    assert len({item["organisation_number"] for item in directory})==300
    assert all(item["registry_source"].endswith("/"+item["organisation_number"]) for item in directory)
    workspace=read("/static/intelligence.html")
    assert "loadDirectory(false)" in workspace and "Compare as " in workspace
    assert "formatFinancial(v,key,f.currency)" in workspace
    assert "What the sources establish" in workspace
    company=json.loads(read("/api/company/923609016"))
    assert company.get("organisation_number")=="923609016"
    last_page=json.loads(read("/api/directory?page=2"))
    assert len(last_page.get("results") or [])>=90
    return {
        "health":"passed",
        "new_homepage_directory":"present",
        "premium_landing":"present",
        "human_readable_financial_and_synthesis":"present",
        "verified_records":len(directory),
        "workspace":"passed",
        "equnior_exact_lookup":"passed",
        "directory_page_2_records":len(last_page["results"]),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempts",type=int,default=24)
    parser.add_argument("--delay-seconds",type=int,default=15)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    last=None
    for n in range(args.attempts):
        try:
            result=check()
            result["production_url"]=BASE
            result["attempt"]=n+1
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(result,indent=2))
            return
        except Exception as exc:
            last=f"{type(exc).__name__}: {exc}"
            print(f"Attempt {n+1}/{args.attempts}: {last}",flush=True)
            if n+1<args.attempts:
                time.sleep(args.delay_seconds)
    raise SystemExit("Production deployment did not pass: "+str(last))


if __name__ == "__main__":
    main()
