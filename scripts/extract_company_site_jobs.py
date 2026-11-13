#!/usr/bin/env python3
"""Conservative structured JobPosting observations from a verified company-owned website.

Never infer that a generic careers page is an open vacancy.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from norway_company_agent.identity import _tokens


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().removeprefix("www.")


def observation(profile: dict) -> dict | None:
    site = (profile.get("evidence") or {}).get("website") or {}
    value = site.get("value") or {}
    identity = value.get("identity_assessment") or {}
    if site.get("status") != "available" or not identity.get("publishable"):
        return None
    final_url = str(value.get("final_url") or site.get("source_url") or "")
    base_host = _host(final_url)
    if not base_host:
        return None
    legal_tokens = set(_tokens(profile.get("name")))
    org = str(profile.get("organisation_number") or "")
    for page in value.get("pages") or []:
        page_url = str(page.get("url") or "")
        if _host(page_url) != base_host:
            continue
        for job in page.get("job_postings") or []:
            if not isinstance(job, dict):
                continue
            title = str(job.get("title") or "").strip()
            posted = str(job.get("datePosted") or "").strip()
            expires = str(job.get("validThrough") or "").strip()
            source_url = str(job.get("url") or page_url)
            source = urlparse(source_url)
            if source.scheme not in {"https", "http"} or _host(source_url) != base_host:
                continue
            if not title or not posted or not re.match(r"^\d{4}-\d{2}-\d{2}", posted):
                continue
            hiring = job.get("hiringOrganization") or {}
            employer_name = hiring.get("name") if isinstance(hiring, dict) else str(hiring)
            employer_tokens = set(_tokens(employer_name))
            # When a structured employer explicitly disagrees with the official
            # legal name, skip it. Subsidiary/parent postings are not target jobs.
            if employer_tokens and not legal_tokens.issubset(employer_tokens):
                continue
            if expires:
                try:
                    expiry = datetime.fromisoformat(expires[:10]).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if expiry.date() < datetime.now(timezone.utc).date():
                    continue
            digest = str(page.get("content_sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest, re.I):
                continue
            return {
                "id": "company-site-job-" + hashlib.sha256(f"{org}|{source_url}".encode()).hexdigest()[:24],
                "organisation_number": org,
                "platform": "company_site",
                "signal_type": "job_posting",
                "source_url": source_url,
                "retrieved_at": site.get("retrieved_at"),
                "published_at": posted,
                "content_sha256": digest,
                "exact_entity": True,
                "identity_proof": [{"type": "verified_company_site", "score": identity.get("score")}],
                "acquisition_mode": "permitted_public_page",
                "rights_status": "approved",
                "source_class": "company_site",
                "evidence_span": title[:200],
                "metrics": {"title": title, "valid_through": expires or None,
                            "opening_status": "not independently verified" if not expires else "not expired according to posted validity"},
                "strategy": "verified_company_site_jobposting",
            }
    return None
