#!/usr/bin/env python3
"""Conservative structured JobPosting observations from a verified company-owned website.

Never infer that a generic careers page is an open vacancy.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone, timedelta, date
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
            # A missing employer is NOT exact-entity evidence. Do not infer it
            # merely from a parent-group page or an inherited site owner.
            if not legal_tokens or not employer_tokens or not legal_tokens.issubset(employer_tokens):
                continue
            # Explicit organisation numbers, when present, must match the
            # Norwegian registry entity; related employers are rejected.
            if isinstance(hiring, dict):
                identifiers = hiring.get("identifier") or hiring.get("taxID")
                candidate_numbers = []
                def collect_identifiers(node):
                    if isinstance(node, dict):
                        for k, v in node.items():
                            if k in ("value", "taxID") and isinstance(v, (str, int)):
                                candidate_numbers.extend(re.findall(r"(?<!\d)\d{9}(?!\d)", str(v)))
                            else:
                                collect_identifiers(v)
                    elif isinstance(node, list):
                        for value in node:
                            collect_identifiers(value)
                    elif isinstance(node, (str, int)):
                        candidate_numbers.extend(re.findall(r"(?<!\d)\d{9}(?!\d)", str(node)))
                collect_identifiers(identifiers)
                if candidate_numbers and org not in candidate_numbers:
                    continue
            try:
                posted_date = date.fromisoformat(posted[:10])
            except ValueError:
                continue
            today = datetime.now(timezone.utc).date()
            # A decade-old jobs page is not an active vacancy. If no
            # validity date is supplied, only very recent listings qualify.
            if posted_date > today + timedelta(days=1):
                continue
            if expires:
                try:
                    expiry = date.fromisoformat(expires[:10])
                except ValueError:
                    continue
                if expiry < today or posted_date < today - timedelta(days=365):
                    continue
            elif posted_date < today - timedelta(days=45):
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
