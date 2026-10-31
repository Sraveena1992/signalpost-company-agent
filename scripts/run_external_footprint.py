#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.external_footprint import aggregate_footprint, publishable_observation  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def site_observations(profile: dict) -> list[dict]:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    identity = value.get("identity_assessment") or {}
    if website.get("status") != "available" or not identity.get("publishable"):
        return []

    org = str(profile["organisation_number"])
    digest = str(value.get("content_sha256") or website.get("content_sha256") or "")
    retrieved = website.get("retrieved_at")
    if len(digest) != 64 or not retrieved:
        return []

    observations: list[dict] = []
    # Only publish item-level observations when the exact fetched company-owned
    # page is available. A generic homepage is not proof of a specific item.
    from urllib.parse import urlparse

    def company_page(page: dict) -> bool:
        url = str(page.get("url") or "")
        parsed = urlparse(url)
        home = urlparse(str(value.get("final_url") or ""))
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.hostname == home.hostname
            and bool(page.get("content_sha256"))
            and len(str(page.get("content_sha256"))) == 64
        )

    for page in value.get("pages") or []:
        if not isinstance(page, dict) or not company_page(page):
            continue
        url = str(page["url"])
        path = urlparse(url).path.lower().rstrip("/")
        if path in {"", "/"}:
            continue
        if any(token in path for token in ("/news/", "/press/", "/aktuelt/", "/nyheter/", "/artikler/", "/blog/")):
            # Category pages alone do not prove an individual article.
            page_hash = str(page["content_sha256"])
            observations.append({
                "id": f"company-site-news-{org}-{page_hash[:16]}",
                "organisation_number": org,
                "platform": "company_site",
                "signal_type": "public_post",
                "source_url": url,
                "retrieved_at": retrieved,
                "content_sha256": page_hash,
                "exact_entity": True,
                "identity_proof": list(identity.get("promotion_proof") or []),
                "acquisition_mode": "permitted_public_page",
                "rights_status": "approved",
                "source_class": "company_site",
                "evidence_span": str(page.get("title") or page.get("main_text_excerpt") or "")[:1200],
                "metrics": {"activity_page": url},
                "strategy": "company_site_activity",
            })

    # Social handles are intentionally not promoted here: the website crawler
    # currently merges links from multiple pages without recording which exact
    # company page contained each handle. Do not invent item-level provenance.
    # Job postings are likewise not emitted without a fetched posting URL.

    return observations


def annual_workforce_observation(profile: dict) -> dict | None:
    # The dedicated annual-report connector remains the authoritative extractor. This
    # adapter only promotes already-produced, approved observations when present.
    for record in (profile.get("external_observations") or []):
        if record.get("signal_type") == "workforce_snapshot" and publishable_observation(record):
            return record
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conservative, evidence-first external footprint observations from a profile batch.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--freshness-days", type=int, default=45)
    args = parser.parse_args()

    profiles = read_jsonl(Path(args.profiles))
    observations: list[dict] = []
    by_org: dict[str, int] = {}
    for profile in profiles:
        org = str(profile["organisation_number"])
        before = len(observations)
        observations.extend(site_observations(profile))
        workforce = annual_workforce_observation(profile)
        if workforce:
            observations.append(workforce)
        by_org[org] = len(observations) - before

    # De-duplicate by observation ID so reruns remain stable.
    unique = {str(item["id"]): item for item in observations}
    observations = list(unique.values())
    observations.sort(key=lambda item: (str(item.get("organisation_number")), str(item.get("id"))))
    accepted = [item for item in observations if publishable_observation(item)]
    footprint = aggregate_footprint(observations, as_of=args.as_of, freshness_days=args.freshness_days)
    report = {
        "connector": "signalpost_external_footprint_orchestrator_v1",
        "profiles": len(profiles),
        "observations": len(observations),
        "publishable_observations": len(accepted),
        "companies_with_observations": sum(value > 0 for value in by_org.values()),
        "observation_counts_by_company": by_org,
        "footprint": footprint,
        "claim_boundary": "Only exact-entity, evidence-complete, approved company-owned observations are promoted. This is not the hidden competition score.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in observations), encoding="utf-8")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "observation_counts_by_company"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
