#!/usr/bin/env python3
"""NAV stilling-feed: exact-org-number verified job enrichment, separate from website crawl.

No network requests on import. Never log credentials. This is an opt-in post-batch
pass over the existing 500 profiles; original profiles are never overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

BASE = "https://pam-stilling-feed.nav.no"
FEED = BASE + "/api/v1/feed"
ORG = re.compile(r"^\d{9}$")
MAX_DETAIL_BYTES = 1_000_000
MAX_PAGE_BYTES = 3_000_000


def utc_now():
    return datetime.now(timezone.utc)


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def nav_url(path):
    """Reject arbitrary domains, credentials, and non-NAV redirects."""
    url = urllib.parse.urljoin(BASE, str(path))
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname != "pam-stilling-feed.nav.no" or p.port not in (None, 443) or p.username or p.password:
        raise ValueError("Unsafe NAV feed URL")
    if not p.path.startswith("/api/v1/") or ".." in urllib.parse.unquote(p.path).split("/"):
        raise ValueError("Unexpected NAV endpoint")
    return url


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        nav_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_json(url, token, max_bytes=MAX_PAGE_BYTES, since=None):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "User-Agent": "signalpost-research/1.0"}
    if since:
        from email.utils import format_datetime
        headers["If-Modified-Since"] = format_datetime(since, usegmt=True)
    req = urllib.request.Request(nav_url(url), headers=headers)
    opener = urllib.request.build_opener(SameHostRedirect())
    with opener.open(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError("NAV HTTP status " + str(response.status))
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("NAV response too large")
        if "json" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("NAV response is not JSON")
        return json.loads(raw)


def feed_events(get, token, *, max_pages, since, now):
    """Read recent feed updates; later events replace earlier events for each UUID."""
    url = FEED
    seen_pages = set()
    latest = {}
    pages = 0
    while url and pages < max_pages:
        canonical = nav_url(url)
        if canonical in seen_pages:
            raise ValueError("Repeated NAV feed page")
        seen_pages.add(canonical)
        page = get(canonical, token, since=since)
        if not isinstance(page, dict) or not isinstance(page.get("items"), list):
            raise ValueError("Malformed NAV feed response")
        pages += 1
        for item in page["items"]:
            if not isinstance(item, dict):
                continue
            hdr = item.get("_feed_entry") or {}
            uid = str(hdr.get("uuid") or "").strip()
            modified = parse_date(item.get("date_modified") or hdr.get("sistEndret"))
            if not uid or modified is None or modified > now + timedelta(days=1):
                continue
            old = latest.get(uid)
            if old is None or modified >= old[0]:
                latest[uid] = (modified, item)
        next_url = page.get("next_url")
        url = next_url if next_url else None
    complete = url is None
    return latest, pages, complete


def qualify(entry, expected_org, now):
    """Only NAV ACTIVE ads with same exact employer orgnr and unexpired dates."""
    if not isinstance(entry, dict):
        return None, "invalid_detail"
    body = entry.get("json") if isinstance(entry.get("json"), dict) else entry
    status = str(entry.get("status") or body.get("status") or "").upper()
    if status != "ACTIVE":
        return None, "inactive_detail"
    employer = body.get("employer") or {}
    org = str(employer.get("orgnr") or "").strip() if isinstance(employer, dict) else ""
    if org != expected_org:
        return None, "employer_orgnr_mismatch"
    published = parse_date(body.get("published"))
    expires = parse_date(body.get("expires"))
    if not published or not expires:
        return None, "missing_dates"
    if published > now + timedelta(days=1) or expires < now or published < now - timedelta(days=190):
        return None, "stale_or_expired"
    title = str(body.get("title") or body.get("jobtitle") or "").strip()
    if not title:
        return None, "missing_title"
    source = body.get("sourceurl") or body.get("link") or body.get("applicationUrl")
    if source:
        parsed = urllib.parse.urlsplit(str(source))
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None, "unsafe_source_url"
    uid = str(body.get("uuid") or entry.get("uuid") or "").strip()
    if not uid:
        return None, "missing_uuid"
    # NAV endpoint is stable source evidence even if external ATS URL is absent.
    detail_url = nav_url("/api/v1/feedentry/" + urllib.parse.quote(uid, safe=""))
    return {
        "vacancy_id": uid, "organisation_number": org, "title": title,
        "published_at": published.isoformat(), "expires_at": expires.isoformat(),
        "source_url": str(source) if source else detail_url,
        "nav_source_url": detail_url,
        "employer_name": str(employer.get("name") or ""),
        "retrieved_at": now.isoformat(),
        "source_class": "nav_official_job_feed",
        "status": "active_at_retrieval",
    }, None


def enrich(profiles, *, get, token, max_pages=250, max_details=10000, since=None, now=None):
    now = now or utc_now()
    since = since or now - timedelta(days=190)
    orgs = {str(p.get("organisation_number") or "") for p in profiles}
    if len(orgs) != len(profiles) or any(not ORG.fullmatch(n) for n in orgs):
        raise ValueError("Duplicate or invalid organisation numbers")
    latest, pages, complete = feed_events(get, token, max_pages=max_pages, since=since, now=now)
    matched = {}
    rejects = {}
    details_checked = 0
    active = [(uid, item) for uid, (modified, item) in latest.items() if (item.get("_feed_entry") or {}).get("status") == "ACTIVE"]
    detail_limit_hit = len(active) > max_details
    for uid, item in active[:max_details]:
        try:
            detail = get(nav_url(item.get("url") or "/api/v1/feedentry/" + urllib.parse.quote(uid, safe="")), token, max_bytes=MAX_DETAIL_BYTES)
            details_checked += 1
            body = detail.get("json") if isinstance(detail, dict) and isinstance(detail.get("json"), dict) else detail
            org = str((body.get("employer") or {}).get("orgnr") or "") if isinstance(body, dict) and isinstance(body.get("employer"), dict) else ""
            if org not in orgs:
                rejects["not_in_batch"] = rejects.get("not_in_batch", 0) + 1
                continue
            job, reason = qualify(detail, org, now)
            if job:
                matched.setdefault(org, {})[job["vacancy_id"]] = job
            else:
                rejects[reason] = rejects.get(reason, 0) + 1
        except (ValueError, KeyError, OSError, RuntimeError) as exc:
            category = "detail_fetch_or_parse_failure"
            rejects[category] = rejects.get(category, 0) + 1
    complete = complete and not detail_limit_hit
    output = []
    for profile in profiles:
        item = dict(profile)
        ev = dict(item.get("evidence") or {})
        number = str(item["organisation_number"])
        jobs = list(matched.get(number, {}).values())
        ev["nav_jobs"] = {
            "field": "nav_jobs",
            "status": "available" if jobs else ("not_found" if complete else "source_error"),
            "source_type": "nav_official_job_feed", "source_url": FEED,
            "retrieved_at": now.isoformat(),
            "value": {"postings": jobs, "checked": True, "scan_complete": complete},
            "note": "No matched active vacancy in completed NAV scan" if complete and not jobs else "Incomplete scan; absence cannot be established" if not complete and not jobs else None,
        }
        item["evidence"] = ev
        output.append(item)
    report = {
        "companies": len(profiles), "matched_companies": sum(bool(matched.get(n)) for n in orgs),
        "verified_active_jobs": sum(len(v) for v in matched.values()),
        "pages_read": pages, "unique_feed_ads": len(latest), "active_ads_examined": details_checked,
        "scan_complete": complete, "max_pages": max_pages, "max_details": max_details,
        "since": since.isoformat(), "checked_at": now.isoformat(), "rejected": rejects,
        "scope": "Exact NAV employer.orgnr matched to the supplied company batch. Incomplete scans are not no-job proof.",
    }
    return output, report


def main():
    ap = argparse.ArgumentParser(description="Exact-org NAV vacancies enrichment (opt-in, no production writes)")
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--token-env", default="NAV_FEED_TOKEN")
    ap.add_argument("--max-pages", type=int, default=250)
    ap.add_argument("--max-details", type=int, default=10000)
    args = ap.parse_args()
    if args.max_pages < 1 or args.max_details < 1:
        ap.error("limits must be positive")
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        ap.error("NAV feed token missing from environment; see official NAV documentation")
    source = Path(args.profiles).resolve()
    output = Path(args.output).resolve()
    if source == output:
        ap.error("Original profile input cannot be overwritten")
    profiles = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        result, report = enrich(profiles, get=fetch_json, token=token, max_pages=args.max_pages, max_details=args.max_details)
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit("NAV scan failed: " + type(exc).__name__ + ": " + str(exc)) from None
    output.parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in result), encoding="utf-8")
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
