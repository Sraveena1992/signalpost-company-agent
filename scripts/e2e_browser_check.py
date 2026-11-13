#!/usr/bin/env python3
"""Chromium browser journey: 300 real companies, A/B comparison and mobile UX."""
from __future__ import annotations

import json
from pathlib import Path

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
        assert page.url.split("#")[0] == original.split("#")[0]
        result["checks"].append("Reload restores shareable comparison")
        page.screenshot(path=str(OUT/"desktop-compare.png"), full_page=False)
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
