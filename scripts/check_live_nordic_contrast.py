#!/usr/bin/env python3
"""Chromium check of real deployed premium site; never a local-only preview."""
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE="https://signalpost-company-agent.onrender.com"
OUT=Path("artifacts/live-nordic-ui")
OUT.mkdir(parents=True,exist_ok=True)

def contrast(locator):
    return locator.evaluate("""el=>{
       const css=getComputedStyle(el);
       function luminance(s){
         const vals=s.match(/[\\d.]+/g).slice(0,3).map(Number);
         const c=vals.map(n=>{n/=255;return n<=.04045?n/12.92:Math.pow((n+.055)/1.055,2.4)});
         return .2126*c[0]+.7152*c[1]+.0722*c[2];
       }
       const x=luminance(css.color),y=luminance(css.backgroundColor);
       return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
    }""")

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    result={"url":BASE,"checks":[]}
    desktop=browser.new_page(viewport={"width":1440,"height":900})
    response=desktop.goto(BASE,wait_until="domcontentloaded",timeout=120000)
    assert response and response.status==200
    desktop.locator(".hero-visual .hero-step").first.wait_for(timeout=45000)
    assert desktop.locator(".hero-visual .hero-step").count()==3
    assert "Every company." in desktop.locator(".hero h1").inner_text()
    a=desktop.locator(".hero-actions a.button.secondary")
    a.wait_for(state="visible")
    primary=desktop.locator(".hero-actions a.button:not(.secondary)")
    assert contrast(a)>=4.5
    assert contrast(primary)>=4.5
    desktop.locator("#featured-more").wait_for(state="visible",timeout=60000)
    assert contrast(desktop.locator("#featured-more"))>=4.5
    result["checks"].append("Desktop premium hero + 3 steps and three CTA labels >=4.5 contrast")
    desktop.screenshot(path=str(OUT/"desktop-premium-home.png"),full_page=False)
    mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1)
    mobile.goto(BASE,wait_until="domcontentloaded",timeout=120000)
    mobile.locator(".hero-visual .hero-step").first.wait_for(timeout=45000)
    width=mobile.evaluate("({scroll:document.documentElement.scrollWidth,inner:window.innerWidth})")
    assert width["scroll"]<=width["inner"]+2,width
    assert contrast(mobile.locator(".hero-actions a.button.secondary"))>=4.5
    result["checks"].append("390px mobile no document horizontal overflow; button readable")
    mobile.screenshot(path=str(OUT/"mobile-premium-home.png"),full_page=False)
    (OUT/"report.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    browser.close()
