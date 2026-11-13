#!/usr/bin/env python3
"""Independently re-check 300 official Norwegian registry entries by exact org number.

Produces registry identities only. Does not assert independent verification of
company website, accounts, people, jobs, news or other research.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"


def fetch_json(url: str) -> dict:
    last = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "SignalpostRegistryAudit/1.0"})
            with urllib.request.urlopen(request, timeout=35) as response:
                return json.loads(response.read(3_000_000).decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep((attempt + 1) * 1.5)
    raise RuntimeError(f"Official registry request failed for {url}: {type(last).__name__}")


def verified_record(candidate: dict) -> dict:
    orgnr = str(candidate.get("organisasjonsnummer") or "")
    if not re.fullmatch(r"\d{9}", orgnr):
        raise ValueError("Invalid Norwegian organisation number")
    detail = fetch_json(BASE + "/" + orgnr)
    if str(detail.get("organisasjonsnummer")) != orgnr or detail.get("navn") != candidate.get("navn"):
        raise ValueError("Registry search result disagrees with exact-organisation detail")
    return {
        "organisation_number": orgnr,
        "name": detail.get("navn"),
        "organisation_form": (detail.get("organisasjonsform") or {}).get("beskrivelse"),
        "industry_code": (detail.get("naeringskode1") or {}).get("kode"),
        "industry": (detail.get("naeringskode1") or {}).get("beskrivelse"),
        "business_address": detail.get("forretningsadresse"),
        "vat_registered": detail.get("registrertIMvaregisteret"),
        "bankruptcy": detail.get("konkurs"),
        "registry_source": BASE + "/" + orgnr,
        "verification": "exact official org-number record and legal-name match",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def verify(count: int = 300, workers: int = 4) -> tuple[list[dict], dict]:
    if not 201 <= count <= 300:
        raise ValueError("Count must be 201–300")
    candidates = []
    for page in range((count + 99) // 100):
        url = BASE + "?" + urllib.parse.urlencode({"page": page, "size": 100, "sort": "organisasjonsnummer,ASC"})
        result = fetch_json(url)
        candidates.extend((result.get("_embedded") or {}).get("enheter") or [])
    candidates = candidates[:count]
    if len(candidates) != count:
        raise RuntimeError(f"Official search returned only {len(candidates)} / {count} candidates")
    records, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(verified_record, candidate): candidate for candidate in candidates}
        for future in concurrent.futures.as_completed(futures):
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append({"organisation_number": str(futures[future].get("organisasjonsnummer") or ""), "reason": str(exc)})
    records.sort(key=lambda row: row["organisation_number"])
    dup = len(records) - len({r["organisation_number"] for r in records})
    report = {
        "requested": count,
        "official_search_candidates": len(candidates),
        "exact_official_details_verified": len(records),
        "duplicate_organisation_numbers": dup,
        "failed_records": errors,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": BASE,
        "interpretation": "Exact official legal entity identity only. Not a complete research or scoring benchmark.",
        "passed": len(records) == count and dup == 0 and not errors,
    }
    return records, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    records, report = verify(args.count, args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
