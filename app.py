
from __future__ import annotations

import html
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(
    title="Signalpost Company Intelligence",
    description="Evidence-linked Norwegian company lookup using the official Brønnøysund Register API.",
    version="1.0.0",
)

REGISTRY_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/"


def lookup_company(orgnr: str) -> dict:
    if not re.fullmatch(r"\d{9}", orgnr):
        raise ValueError("Enter a valid 9-digit Norwegian organisation number.")

    request = Request(
        REGISTRY_URL + orgnr,
        headers={"Accept": "application/json", "User-Agent": "SignalpostCompanyAgent/1.0"},
    )

    try:
        with urlopen(request, timeout=12) as response:
            company = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise LookupError("No company was found for this organisation number.") from exc
        raise RuntimeError(f"The official registry returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("The official registry could not be reached. Please retry.") from exc

    address = company.get("forretningsadresse") or {}
    address_lines = address.get("adresse") or []
    industry = company.get("naeringskode1") or {}
    org_form = company.get("organisasjonsform") or {}

    return {
        "organisation_number": company.get("organisasjonsnummer", orgnr),
        "name": company.get("navn"),
        "organisation_form": org_form.get("beskrivelse"),
        "business_address": ", ".join(
            str(part) for part in [
                *address_lines,
                address.get("postnummer"),
                address.get("poststed"),
                address.get("kommune"),
                address.get("land"),
            ] if part
        ) or None,
        "industry_code": industry.get("kode"),
        "industry": industry.get("beskrivelse"),
        "website": company.get("hjemmeside"),
        "registered_for_vat": company.get("registrertIMvaregisteret"),
        "bankruptcy": company.get("konkurs"),
        "registry_source": REGISTRY_URL + orgnr,
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "signalpost-company-agent"}


@app.get("/api/company/{orgnr}")
def company_api(orgnr: str):
    try:
        return lookup_company(orgnr)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})


@app.get("/", response_class=HTMLResponse)
def home(orgnr: str = Query(default="", max_length=30)):
    result_html = ""

    if orgnr:
        try:
            company = lookup_company(orgnr.strip())
            fields = [
                ("Legal name", company["name"]),
                ("Organisation number", company["organisation_number"]),
                ("Organisation type", company["organisation_form"]),
                ("Business address", company["business_address"]),
                ("Industry", company["industry"]),
                ("Industry code", company["industry_code"]),
                ("VAT registered", company["registered_for_vat"]),
                ("Bankruptcy", company["bankruptcy"]),
                ("Website", company["website"]),
            ]
            rows = "".join(
                "<tr><th>" + html.escape(label) + "</th><td>" +
                html.escape(str(value)) + "</td></tr>"
                for label, value in fields if value is not None
            )
            source = html.escape(company["registry_source"], quote=True)
            result_html = (
                '<section class="result"><p class="eyebrow">OFFICIAL REGISTRY RESULT</p>'
                '<h2>' + html.escape(str(company["name"] or "Company record")) + '</h2>'
                '<table>' + rows + '</table>'
                '<p><a target="_blank" rel="noopener noreferrer" href="' + source +
                '">Open original registry record ↗</a></p></section>'
            )
        except (ValueError, LookupError, RuntimeError) as exc:
            result_html = '<section class="error">' + html.escape(str(exc)) + '</section>'

    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signalpost | Company Intelligence</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#141d31;--line:#293750;--muted:#a8b7cd;--accent:#83f0c2}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 15% 0%,#183c48 0,transparent 42%),var(--bg);color:#f3f7ff;font:16px/1.6 system-ui,sans-serif}
main{max-width:900px;margin:0 auto;padding:34px 22px 70px}.brand{font-size:14px;letter-spacing:2px;font-weight:800;color:var(--accent)}
.hero{padding:55px 0 28px}h1{font-size:clamp(36px,7vw,62px);line-height:1.06;letter-spacing:-2px;margin:12px 0 18px}.sub{color:var(--muted);max-width:650px}
.panel,.result{border:1px solid var(--line);border-radius:20px;background:rgba(20,29,49,.92);padding:24px;margin:20px 0}
label{display:block;font-weight:650;margin-bottom:10px}form{display:flex;gap:10px;flex-wrap:wrap}input{flex:1;min-width:200px;padding:15px;border:1px solid #3b4b67;border-radius:10px;background:#0b1222;color:white;font:inherit}
button{padding:15px 20px;border:0;border-radius:10px;background:var(--accent);color:#071c18;font-weight:800;font:inherit;cursor:pointer}
.eyebrow{font-size:12px;letter-spacing:1.5px;color:var(--accent);font-weight:800}table{width:100%;border-collapse:collapse;margin:20px 0}th,td{text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);width:35%;font-weight:500}a{color:var(--accent);overflow-wrap:anywhere}.error{padding:16px;border:1px solid #a45c68;background:#361e2a;border-radius:12px}.meta{font-size:13px;color:var(--muted)}.pill{display:inline-block;border:1px solid #3a6e61;color:var(--accent);border-radius:20px;padding:4px 10px;font-size:12px}
@media(max-width:540px){main{padding:24px 15px}.panel,.result{padding:17px}form button{width:100%}th{width:42%}}
</style>
</head>
<body><main>
<div class="brand">SIGNALPOST <span class="pill">LIVE PROTOTYPE</span></div>
<header class="hero"><p class="eyebrow">COMPANY INTELLIGENCE · NORWAY</p>
<h1>Know the company.<br>Verify the evidence.</h1>
<p class="sub">Look up a Norwegian organisation using its 9-digit number. Start with the official Brønnøysund Register and follow the source for yourself.</p></header>
<section class="panel"><form method="get" action="/">
<div style="flex:1;min-width:200px"><label for="orgnr">Organisation number</label>
<input id="orgnr" name="orgnr" inputmode="numeric" pattern="[0-9]{9}" maxlength="9" placeholder="e.g. 923 609 016" value=""" + html.escape(orgnr, quote=True) + """ required></div>
<button type="submit" style="align-self:end">Research company ↗</button></form>
<p class="meta">Live public registry lookup · Source-linked fields · No precomputed company profile</p></section>
""" + result_html + """
<section class="panel"><p class="eyebrow">EVIDENCE FIRST</p><h2>Designed for verifiable research</h2>
<p class="sub">This public demo currently provides an official-registry lookup. It is not the full batch research pipeline and does not claim to verify every company fact or financial result.</p>
<p class="meta">Source: <a href="https://www.brreg.no/en/" target="_blank" rel="noopener noreferrer">Brønnøysund Register Centre</a> · <a href="/docs">Explore the JSON API ↗</a> · <a href="/healthz">Service health ↗</a></p></section>
<footer class="meta">Signalpost Company Intelligence · Prototype · Registry data may be incomplete or change over time.</footer>
</main></body></html>"""
    )
