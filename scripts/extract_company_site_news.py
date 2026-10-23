#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


NEWS_PATH = re.compile(r"/(?:news|press|aktuelt|nyheter|artikler|blog)(?:/|$)", re.I)
GENERIC_TOKENS = {"as", "asa", "ans", "da", "enk", "iks", "sa", "sam", "nuf", "ab", "ltd", "limited", "inc", "the", "og", "and"}


def _tokens(value: str) -> list[str]:
    value = value.translate(str.maketrans({"ø": "o", "Ø": "O", "å": "a", "Å": "A", "æ": "ae", "Æ": "AE"}))
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return [token for token in re.findall(r"[a-z0-9]+", value) if len(token) > 1 and token not in GENERIC_TOKENS]


def observation(profile: dict) -> dict | None:
    website = (profile.get("evidence") or {}).get("website") or {}
    value = website.get("value") or {}
    identity = value.get("identity_assessment") or {}
    if website.get("status") != "available" or not identity.get("publishable"):
        return None
    generic_titles = {
        "news", "press", "newsroom", "aktuelt", "nyheter", "blog", "blogg",
        "contact", "kontakt", "about us", "om oss", "products", "produkter",
        "services", "tjenester", "home", "homepage",
    }
    pages = []
    company_tokens = set(_tokens(str(profile.get("name") or "")))
    if not company_tokens:
        return None
    for page in (value.get("pages") or []):
        path = urlparse(str(page.get("url") or "")).path
        title = str(page.get("title") or "").strip()
        published_at = str(page.get("published_at") or "").strip()
        excerpt = str(page.get("main_text_excerpt") or "").strip()
        article_tokens = set(_tokens(title + " " + excerpt))
        # A URL under /news/ is not proof of a news item. Require an explicit
        # publication date, article markup, meaningful text, a non-menu title,
        # and exact legal-name token coverage in the article itself.
        if (
            NEWS_PATH.search(path)
            and published_at
            and page.get("article_like") is True
            and len(excerpt) >= 120
            and title.casefold() not in generic_titles
            and company_tokens.issubset(article_tokens)
        ):
            pages.append(page)
    if not pages:
        return None
    # Prefer an individual article over an archive page when the bounded crawl
    # captured both. One observation is enough to prove site activity without
    # rewarding a site for repeated navigation links.
    pages.sort(key=lambda page: (-len([part for part in urlparse(str(page.get("url") or "")).path.split("/") if part]), str(page.get("url") or "")))
    page = pages[0]
    url = str(page.get("url") or "")
    digest = str(page.get("content_sha256") or "")
    if not url.startswith(("http://", "https://")) or len(digest) != 64:
        return None
    org = str(profile["organisation_number"])
    title = str(page.get("title") or "Company news/activity page").strip()
    return {
        "id": "company-site-news-" + hashlib.sha256(f"{org}|{url}".encode()).hexdigest()[:24],
        "organisation_number": org,
        "platform": "company_site",
        "signal_type": "public_post",
        "source_url": url,
        "retrieved_at": website.get("retrieved_at"),
        "published_at": str(page.get("published_at") or ""),
        "content_sha256": digest,
        "exact_entity": True,
        "identity_proof": [{"type": "website_identity_gate", "score": identity.get("score"), "method": identity.get("method")}],
        "acquisition_mode": "permitted_public_page",
        "rights_status": "approved",
        "source_class": "company_site",
        "evidence_span": title[:1200],
        "metrics": {"captured_news_pages": len(pages), "interpretation": "Company-owned activity; not independent sentiment."},
        "strategy": "company_site_activity",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract company-owned activity from exact-site bounded news pages.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    profiles = [json.loads(line) for line in Path(args.profiles).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [item for profile in profiles if (item := observation(profile))]
    Path(args.output).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {
        "connector": "exact_company_site_news_activity_v1",
        "profiles": len(profiles),
        "companies_with_activity": len(rows),
        "observations": len(rows),
        "claim_boundary": "Company-owned activity only; never treated as independent sentiment.",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
