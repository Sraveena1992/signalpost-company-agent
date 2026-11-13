#!/usr/bin/env python3
"""Chromium browser journey: 300 real companies, A/B comparison and mobile UX."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
OUT = Path("artifacts/browser-smoke")
OUT.mkdir(parents=True, exist_ok=True)


def main():
    result = {"checks": [], "console_errors": [], "mobile_overflow": None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1365, "height": 900}, device_scale_factor=1)
        page.on("pageerror", lambda e: result["console_errors"].append(str(e)))
        response = page.goto(BASE + "/static/intelligence.html", wait_until="domcontentloaded", timeout=60000)
        assert response and response.status == 200
        page.locator("#directoryCount").get_by_text("300 shown").wait_for(timeout=60000)
        assert page.locator("#results article.hit").count() == 300
        result["checks"].append("300 verified registry companies rendered automatically")
        page.screenshot(path=str(OUT/"desktop-directory.png"), full_page=False)
        page.locator("#filterDirectory").fill("SANDNES ELEKTRISKE")
        assert page.locator("#results article.hit").count() >= 1
        assert page.locator("#results article.hit").count() < 300
        result["checks"].append("Directory search filter works")
        page.locator("#filterDirectory").fill("")
        page.locator("#results article.hit").filter(has_text="SANDNES ELEKTRISKE AS").get_by_role("button", name="Compare as A").click()
        page.wait_for_timeout(3000)
        print("DIAGNOSTIC_A", json.dumps({"status":page.locator("#compareStatus").inner_text(),"name":page.locator("#aname").inner_text(),"url":page.url}),flush=True)
        page.locator("#aname").filter(has_text="SANDNES ELEKTRISKE AS").wait_for(timeout=30000)
        assert "a=810034882" in page.url
        result["checks"].append("Company A selected through real registry API")
        page.locator("#results article.hit").filter(has_text="WEBLANCE AS").get_by_role("button", name="Compare as B").click()
        page.locator("#bname").filter(has_text="WEBLANCE AS").wait_for(timeout=30000)
        assert "b=811695602" in page.url
        assert page.locator("#registryBody").inner_text().find("SANDNES ELEKTRISKE") >= 0
        result["checks"].append("Company B and comparison facts loaded")
        page.locator("#swap").click()
        assert page.locator("#aname").inner_text() == "WEBLANCE AS"
        result["checks"].append("Swap preserves comparison state")
        original = page.url
        page.reload(wait_until="domcontentloaded")
        page.locator("#aname").filter(has_text="WEBLANCE AS").wait_for(timeout=30000)
        page.locator("#bname").filter(has_text="SANDNES ELEKTRISKE AS").wait_for(timeout=30000)
        assert parse_qs(urlparse(page.url).query) == parse_qs(urlparse(original).query)
        result["checks"].append("Reload restores shareable comparison")
        page.screenshot(path=str(OUT/"desktop-compare.png"), full_page=False)
        # UI-only fixture: assert structured source-linked research renders as readable
        # prose, not serialized JSON. This DOES NOT validate external financial data.
        sample={
            "run_id":"browser-test-only",
            "profile":{
                "organisation_number":"811695602","name":"WEBLANCE AS",
                "evidence":{
                    "financials":{
                        "status":"available",
                        "source_url":"https://data.brreg.no/regnskapsregisteret/regnskap/811695602",
                        "retrieved_at":"2026-11-13T10:00:00Z",
                        "value":{"records":[{"period":{"fraDato":"2025-01-01","tilDato":"2025-12-31"},
                                           "account_type":"SELSKAP","currency":"NOK",
                                           "revenue":12345678,"operating_result":210000,
                                           "annual_result":180000,"assets":9999999,"debt":3000000}]}
                    },
                },
                "synthesis":{
                    "overview":[{"text":"Sample entity's registry identity was verified (synthetic browser fixture).",
                                 "source_url":"https://data.brreg.no/enhetsregisteret/api/enheter/811695602",
                                 "retrieved_at":"2026-11-13T10:00:00Z"}],
                    "unknowns":[{"topic":"job vacancies","state":"not_verified","explanation":"No employer-owned dated posting validated."}],
                    "what_changed":{"status":"no_previous_snapshot","change_count":0},
                    "facts":[{"claim":"Year-over-year revenue change",
                              "value":{"current_year":2025,"previous_year":2024,"percentage_change":17.56},
                              "source_url":"https://data.brreg.no/regnskapsregisteret/regnskap/811695602"}]
                }
            }
        }
        page.route("**/api/research/811695602",lambda route:route.fulfill(
            status=200,content_type="application/json",body=json.dumps(sample)))
        page.locator("#aresearch").click()
        page.locator("#aevidence .synthesis-card").wait_for(timeout=20000)
        assert "What the sources establish" in page.locator("#aevidence").inner_text()
        assert "job vacancies" in page.locator("#aevidence").inner_text()
        assert "Current year: 2025" in page.locator("#aevidence").inner_text()
        assert "12,345,678 NOK" in page.locator("#financialBody").inner_text()
        assert '{"current_year"' not in page.locator("#aevidence").inner_text()
        page.screenshot(path=str(OUT/"desktop-readable-evidence.png"),full_page=False)
        result["checks"].append("Mock research contract renders readable financials, sourced synthesis and explicit gaps")
        # Verify the primary landing page displays the audited directory without navigating away.
        landing = browser.new_page(viewport={"width":1365,"height":900})
        landing.on("pageerror", lambda e: result["console_errors"].append(str(e)))
        landing.goto(BASE+"/",wait_until="domcontentloaded")
        landing.locator("#featured-status").filter(has_text="300 legal entities").wait_for(timeout=45000)
        assert landing.locator("#featured-results article.company-card").count() == 12
        landing.locator("#featured-filter").fill("WEBLANCE")
        assert landing.locator("#featured-results article.company-card").count() == 1
        assert "WEBLANCE" in landing.locator("#featured-results").inner_text()
        landing.screenshot(path=str(OUT/"desktop-homepage-directory.png"),full_page=False)
        landing.close()
        result["checks"].append("Homepage shows 300 independently verified records with working filtering")
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="domcontentloaded")
        page.locator("#aname").get_by_text("WEBLANCE AS").wait_for(timeout=30000)
        width = page.evaluate("({scroll:document.documentElement.scrollWidth,inner:window.innerWidth})")
        result["mobile_overflow"] = width
        assert width["scroll"] <= width["inner"] + 2, width
        page.screenshot(path=str(OUT/"mobile-compare.png"), full_page=False)
        result["checks"].append("390px mobile comparison has no document-level horizontal overflow")
        browser.close()
    assert not result["console_errors"], result["console_errors"]
    (OUT/"browser-report.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
