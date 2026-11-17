"""Regression: standalone news export must match multi-article batch semantics."""
import json
import sys
from scripts import extract_company_site_news as news


def test_cli_exports_each_verified_article_once(tmp_path, monkeypatch):
    excerpt = "Fjellkraft AS has published an important update for stakeholders. " * 4
    pages = [
        {
            "url": "https://fjellkraft.example/nyheter/" + slug,
            "title": "Fjellkraft AS update " + slug,
            "published_at": "2026-11-11",
            "main_text_excerpt": excerpt,
            "article_like": True,
            "content_sha256": "b" * 64,
        }
        for slug in ("first", "second", "first")
    ]
    profile = {
        "organisation_number": "123456785",
        "name": "Fjellkraft AS",
        "evidence": {
            "website": {
                "status": "available",
                "source_url": "https://fjellkraft.example/",
                "retrieved_at": "2026-11-12T12:00:00Z",
                "value": {
                    "final_url": "https://fjellkraft.example/",
                    "identity_assessment": {"publishable": True},
                    "pages": pages,
                },
            }
        },
    }
    inp, out, report = (tmp_path / name for name in ("profiles.jsonl", "news.jsonl", "report.json"))
    inp.write_text(json.dumps(profile) + "\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["extract_company_site_news.py", "--profiles", str(inp), "--output", str(out), "--report", str(report)])
    news.main()
    results = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(report.read_text(encoding="utf-8"))
    assert len(results) == 2
    assert len({item["source_url"] for item in results}) == 2
    assert summary["profiles"] == 1
    assert summary["companies_with_activity"] == 1
    assert summary["observations"] == 2
