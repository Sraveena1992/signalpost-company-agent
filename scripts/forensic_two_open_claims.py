#!/usr/bin/env python3
"""Read-only, bounded original publisher evidence for the two open adjudications.

Never converts a current-source disagreement into a historical gold label.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


TARGETS = {
    "995311321": "https://www.1hjelp.no/",
    "987531630": "https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/",
}
MAX_BYTES = 1_500_000


class PublisherEvidence(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = []
        self.time = []
        self.texts = []
        self._capture = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property") or attrs.get("itemprop")
            if key and attrs.get("content"):
                self.meta.append({"field": key, "value": attrs["content"][:1000]})
        if tag == "time":
            self.time.append({"datetime": attrs.get("datetime"), "text": ""})
        if tag in ("title", "h1", "h2", "time", "p"):
            self._capture = True

    def handle_endtag(self, tag):
        if tag in ("title", "h1", "h2", "time", "p"):
            self._capture = False

    def handle_data(self, data):
        if self._capture and data.strip():
            self.texts.append(data.strip()[:1000])


def extract_raw_evidence(raw):
    parser = PublisherEvidence()
    parser.feed(raw.decode("utf-8", errors="replace"))
    display_text = " ".join(parser.texts)[:10000]
    return {
        "meta": parser.meta[:120],
        "time_tags": parser.time[:20],
        "article_visible_dates": list(dict.fromkeys(re.findall(
            r"(?i)\b(?:\d{1,2}\s+(?:januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)\s*,?\s*20\d{2}|20\d{2}-\d{2}-\d{2})\b",
            display_text)))[:30],
        "title_and_article_excerpts": display_text[:3500],
    }


def forensic_fetch(org, url):
    now = datetime.now(timezone.utc).isoformat()
    request = Request(url, headers={
        "User-Agent": "SignalpostSourceAudit/1.0 (+https://signalpost-company-agent.onrender.com)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8",
    })
    try:
        with urlopen(request, timeout=18) as response:
            status = response.status
            final_url = response.url
            headers = dict(response.headers)
            raw = response.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:
            return {"organisation_number": org, "url": url, "retrieved_at": now, "state": "too_large"}
        observed = extract_raw_evidence(raw)
        return {
            "organisation_number": org, "requested_url": url,
            "final_url": final_url, "retrieved_at": now,
            "http_status": status, "content_type": headers.get("Content-Type"),
            "last_modified": headers.get("Last-Modified"),
            "etag": headers.get("ETag"), "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
            "html_size_bytes": len(raw), "observation": observed,
            "adjudication": "UNRESOLVED_PENDING_ORIGINAL_TIMESTAMPED_SNAPSHOT_OR_HUMAN_REVIEW",
        }
    except Exception as exc:
        return {"organisation_number": org, "url": url, "retrieved_at": now,
                "state": "source_unavailable", "error_type": type(exc).__name__,
                "adjudication": "UNVERIFIABLE"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = {
        "purpose": "Original-source metadata inspection, NOT independent accuracy certification",
        "records": [forensic_fetch(org, url) for org, url in TARGETS.items()],
        "known_disputes": {
            "995311321": "Archived website description differs from later live metadata; temporal drift vs extraction error unresolved",
            "987531630": "Archived source date 2026-05-14; original article's visible Norwegian date appears as 24 juli 2026; verify source temporal metadata and body before adjudication",
        },
        "gold_accuracy_established": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"records":len(out["records"]), "states":[x.get("http_status") or x.get("state") for x in out["records"]]}))


if __name__ == "__main__":
    main()
