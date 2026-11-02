#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.discovery import (
    build_company_search_query,
    score_search_candidate,
)
from norway_company_agent.identity import apply_website_identity_gate
from norway_company_agent.website import fetch_website

ENDPOINT = "https://api.tavily.com/search"


def search(profile, api_key):
    query = build_company_search_query(profile)
    payload = json.dumps({
        "query": query,
        "search_depth": "basic",
        "max_results": 10,
        "include_answer": False,
        "include_raw_content": False,
    }).encode("utf-8")

    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)

    return [
        {
            "url": result.get("url"),
            "title": result.get("title", ""),
            "snippet": result.get("content", ""),
            "rank": index,
            "provider": "tavily",
        }
        for index, result in enumerate(data.get("results", []), 1)
        if isinstance(result, dict) and result.get("url")
    ]


def discover(profile, api_key):
    results = search(profile, api_key)
    candidates = [
        score_search_candidate(profile, result)
        for result in results
    ]

    candidates = [
        item for item in candidates
        if item.get("publishable_candidate")
    ]

    candidates.sort(
        key=lambda item: -item.get("score", 0)
    )

    attempts = []
    crawl_metrics = {
        "requests": 0,
        "bytes": 0,
        "latencies_ms": [],
    }

    for candidate in candidates[:5]:
        try:
            website, operations = fetch_website(
                candidate["url"],
                timeout=15,
            )
            crawl_metrics["requests"] += operations.get("requests", 0)
            crawl_metrics["bytes"] += operations.get("bytes", 0)
            crawl_metrics["latencies_ms"].extend(
                operations.get("latencies_ms", [])
            )
            gated = apply_website_identity_gate(
                profile,
                website,
            )
            assessment = gated.get("assessment") or {}
            verified = (
                website.get("status") == "available"
                and assessment.get("publishable") is True
            )

            attempts.append({
                "url": candidate["url"],
                "verified": verified,
                "requests": operations.get("requests", 0),
            })

            if verified:
                return {
                    "status": "verified",
                    "website_url": website.get("source_url"),
                    "website_record": gated["website"],
                    "crawl_metrics": crawl_metrics,
                    "attempts": attempts,
                }

        except (ValueError, OSError, TimeoutError) as exc:
            attempts.append({
                "url": candidate["url"],
                "verified": False,
                "error": type(exc).__name__,
            })

    return {
        "status": "not_verified",
        "website_url": None,
        "attempts": attempts,
        "search_results": len(results),
        "crawl_metrics": crawl_metrics,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--org", required=True)
    parser.add_argument("--municipality", default="")
    args = parser.parse_args()

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        parser.error("TAVILY_API_KEY is not configured")

    profile = {
        "name": args.name,
        "organisation_number": args.org,
        "municipality": args.municipality,
    }

    result = discover(profile, api_key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
