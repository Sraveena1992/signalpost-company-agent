#!/usr/bin/env python3
"""Sample 1,000 *eligible* companies from Builderr's public 411,160-company universe.

This never reads or claims Builderr's private post-cutoff batch. Input archive
integrity MUST match both published hashes from the August 2026 contract.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

URL="https://builderr.ai/signalpost-company-universe-2025.jsonl.gz"
COMPRESSED_SHA="1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384"
UNCOMPRESSED_SHA="b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838"
EXPECTED=411160


def download(destination):
    request=Request(URL,headers={"User-Agent":"SignalpostEligibleUniverseAudit/1.0","Accept":"application/gzip"})
    with urlopen(request,timeout=180) as resp, destination.open("wb") as out:
        if resp.url.split("/")[2] not in ("builderr.ai","www.builderr.ai"):
            raise ValueError("Unexpected public-universe download destination")
        digest=hashlib.sha256()
        count=0
        for chunk in iter(lambda:resp.read(1024*1024),b""):
            count+=len(chunk)
            if count>160_000_000:
                raise ValueError("Public-universe archive exceeds safe size limit")
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest()!=COMPRESSED_SHA:
        raise ValueError("Builderr public-universe gzip SHA-256 differs from published contract")
    return count


def sample(source):
    sha=hashlib.sha256()
    companies=set()
    with gzip.open(source,"rb") as reader:
        for raw_line in reader:
            sha.update(raw_line)
            if not raw_line.strip():continue
            record=json.loads(raw_line.decode("utf-8-sig"))
            if isinstance(record,dict):
                org=(record.get("organisation_number") or record.get("organisasjonsnummer")
                     or record.get("orgnr") or record.get("org_number"))
            elif isinstance(record,(str,int)):
                org=record
            else:
                raise ValueError("Unsupported public-universe JSONL row type")
            org=str(org or "").strip()
            if not re.fullmatch(r"[0-9]{9}",org):
                raise ValueError("Public universe contained invalid organisation number")
            companies.add(org)
    if sha.hexdigest()!=UNCOMPRESSED_SHA:
        raise ValueError("Builderr public-universe uncompressed SHA-256 mismatch")
    if len(companies)!=EXPECTED:
        raise ValueError(f"Expected {EXPECTED} eligible unique orgs, found {len(companies)}")
    return sorted(companies,key=lambda org:hashlib.sha256(("signalpost-eligible-local-1000-20261115|"+org).encode()).digest())[:1000]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--directory",type=Path,required=True)
    args=ap.parse_args()
    folder=args.directory
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/"public-universe.jsonl.gz"
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest()!=COMPRESSED_SHA:
        download(archive)
    numbers=sample(archive)
    if len(numbers)!=1000 or len(set(numbers))!=1000:
        raise ValueError("Failed to select 1,000 distinct eligible companies")
    (folder/"input-eligible-1000.jsonl").write_text(
        "".join(json.dumps({"organisation_number":n})+"\n" for n in numbers),encoding="utf-8")
    (folder/"eligibility-manifest.json").write_text(json.dumps({
        "public_universe":URL,
        "public_universe_size":EXPECTED,
        "compressed_sha256":COMPRESSED_SHA,
        "uncompressed_sha256":UNCOMPRESSED_SHA,
        "sample_size":1000,
        "batch_type":"PUBLIC_ELIGIBLE_LOCAL_SCALE_NOT_PRIVATE_OFFICIAL",
        "not_official":"Only Builderr supplies and scores the current hidden shared post-cutoff company batch."
    },indent=2)+"\n",encoding="utf-8")
    print("Exactly 1000 eligible public universe company identifiers selected and both hashes checked.")


if __name__=="__main__":
    main()
