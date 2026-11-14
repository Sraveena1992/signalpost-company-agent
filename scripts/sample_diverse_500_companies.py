#!/usr/bin/env python3
"""500 reproducibly sampled 2025 active filers from full official Brreg CSV.

Unlike page=0 browsing, this samples the entire national public registry.
This is not Builderr's private holdout set.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"src"))
from scripts.run_100_company_smoke import ensure_snapshot
from norway_company_agent.sampling import deterministic_financial_filer_sample

DIRECTORY=Path("artifacts/diverse-500")
SNAPSHOT=Path(".smoke-data/brreg-entities.csv.gz")
SEED=20261114
def main():
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    SNAPSHOT.parent.mkdir(parents=True,exist_ok=True)
    ensure_snapshot(SNAPSHOT)
    selected,meta=deterministic_financial_filer_sample(
        SNAPSHOT,500,latest_year="2025",seed=SEED)
    if len(selected)!=500 or len({row["organisation_number"] for row in selected})!=500:
        raise RuntimeError("Invalid diverse 500-company sample")
    orgs=[row["organisation_number"] for row in selected]
    (DIRECTORY/"input-500.json").write_text(json.dumps(orgs,indent=2)+"\n",encoding="utf-8")
    reference=[{
        "organisation_number":row["organisation_number"],
        "name":row.get("name"),"legal_form":row.get("legal_form"),
        "industry_code":row.get("industry_code"),"municipality_number":row.get("municipality_number"),
        "latest_submitted_accounts":row.get("latest_submitted_accounts"),
        "evaluation_split":row.get("evaluation_split"),
        "sample_slice":row.get("sample_slice"),
    } for row in selected]
    (DIRECTORY/"reference-500.json").write_text(json.dumps({
        "selection":"deterministic full national public registry financial-filer sample",
        "not_Builderr_hidden":True,
        "source":"https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
        "metadata":meta,"records":reference,
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"source_rows":meta.get("registry_rows"),
                      "eligible_2025_active_filers":meta.get("eligible_rows"),
                      "selected":len(selected),
                      "legal_form_counts":meta.get("legal_form_counts"),
                      "evaluation_splits":meta.get("evaluation_splits")},ensure_ascii=False,indent=2),flush=True)
if __name__=="__main__":main()
