from __future__ import annotations

import html
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(
    title="Signalpost Company Intelligence",
    description="Evidence-linked Norwegian company lookup using the official Brønnøysund Register API.",
    version="1.1.0",
)

REGISTRY_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/"
REGISTRY_SEARCH_URL = REGISTRY_URL


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SignalpostCompanyAgent/1.1"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise LookupError("No company was found. Check the details and try again.") from exc
        raise RuntimeError(f"The official registry returned HTTP {exc.code}. Please retry.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("The official registry could not be reached. Please retry in a moment.") from exc


def lookup_company(orgnr: str) -> dict:
    orgnr = re.sub(r"\s+", "", orgnr or "")
    if not re.fullmatch(r"\d{9}", orgnr):
        raise ValueError("Enter a valid 9-digit Norwegian organisation number.")
    company = _get_json(REGISTRY_URL + orgnr)
    address = company.get("forretningsadresse") or {}
    industry = company.get("naeringskode1") or {}
    org_form = company.get("organisasjonsform") or {}
    address_lines = address.get("adresse") or []
    return {
        "organisation_number": company.get("organisasjonsnummer", orgnr),
        "name": company.get("navn"),
        "organisation_form": org_form.get("beskrivelse"),
        "business_address": ", ".join(str(part) for part in [
            *address_lines, address.get("postnummer"), address.get("poststed"),
            address.get("kommune"), address.get("land")
        ] if part) or None,
        "industry_code": industry.get("kode"),
        "industry": industry.get("beskrivelse"),
        "website": company.get("hjemmeside"),
        "registered_for_vat": company.get("registrertIMvaregisteret"),
        "bankruptcy": company.get("konkurs"),
        "registry_source": REGISTRY_URL + orgnr,
    }


def search_companies(query: str, size: int = 10) -> list[dict]:
    query = (query or "").strip()
    if len(query) < 2:
        raise ValueError("Enter at least 2 characters of a company name, or a 9-digit organisation number.")
    if len(query) > 120:
        raise ValueError("Company search must be 120 characters or fewer.")
    params = urlencode({"navn": query, "size": min(max(size, 1), 20)})
    payload = _get_json(REGISTRY_SEARCH_URL + "?" + params)
    embedded = payload.get("_embedded") or {}
    entities = embedded.get("enheter") or embedded.get("entities") or []
    results = []
    for entity in entities:
        orgnr = str(entity.get("organisasjonsnummer") or "")
        if not re.fullmatch(r"\d{9}", orgnr):
            continue
        address = entity.get("forretningsadresse") or {}
        address_parts = address.get("adresse") or []
        address_text = ", ".join(str(part) for part in [
            *address_parts, address.get("postnummer"), address.get("poststed"), address.get("kommune")
        ] if part)
        industry = entity.get("naeringskode1") or {}
        results.append({
            "name": entity.get("navn") or "Unnamed organisation",
            "organisation_number": orgnr,
            "organisation_form": (entity.get("organisasjonsform") or {}).get("beskrivelse"),
            "address": address_text,
            "industry": industry.get("beskrivelse"),
        })
    return results


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


@app.get("/api/search")
def company_search_api(q: str = Query(min_length=2, max_length=120), size: int = Query(default=10, ge=1, le=20)):
    try:
        return {"query": q.strip(), "results": search_companies(q, size)}
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})


def _company_result(company: dict) -> str:
    fields = [
        ("Legal name", company.get("name")),
        ("Organisation number", company.get("organisation_number")),
        ("Organisation type", company.get("organisation_form")),
        ("Business address", company.get("business_address")),
        ("Industry", company.get("industry")),
        ("Industry code", company.get("industry_code")),
        ("VAT registered", "Yes" if company.get("registered_for_vat") is True else "No" if company.get("registered_for_vat") is False else "Not stated"),
        ("Bankruptcy", "Yes" if company.get("bankruptcy") is True else "No" if company.get("bankruptcy") is False else "Not stated"),
        ("Website", company.get("website")),
    ]
    rows = "".join(
        "<tr><th>" + html.escape(label) + "</th><td>" + html.escape(str(value)) + "</td></tr>"
        for label, value in fields if value is not None
    )
    source = html.escape(str(company.get("registry_source") or ""), quote=True)
    return (
        '<section class="result"><div class="section-kicker">OFFICIAL REGISTRY RESULT</div>'
        '<h2>' + html.escape(str(company.get("name") or "Company record")) + '</h2>'
        '<table>' + rows + '</table>'
        '<a class="source-link" target="_blank" rel="noopener noreferrer" href="' + source + '">Open original registry record ↗</a>'
        '<div class="result-actions"><a class="button secondary" href="/">↺ New search</a></div></section>'
    )


def _search_results(query: str, results: list[dict]) -> str:
    if not results:
        return '<section class="result"><h2>No matching companies found</h2><p class="muted">Try a shorter name, a different spelling, or the organisation number.</p><a class="button secondary" href="/">↺ Reset search</a></section>'
    cards = []
    for item in results:
        name = html.escape(str(item.get("name") or "Unnamed organisation"))
        orgnr = html.escape(str(item.get("organisation_number") or ""), quote=True)
        form = html.escape(str(item.get("organisation_form") or "Organisation"))
        address = html.escape(str(item.get("address") or "Address not listed"))
        industry = html.escape(str(item.get("industry") or "Industry not listed"))
        cards.append(
            '<article class="match"><div><div class="match-type">' + form + '</div><h3>' + name + '</h3>'
            '<p class="muted">Org. no. ' + orgnr + ' · ' + address + '</p><p class="muted">' + industry + '</p></div>'
            '<a class="button small" href="/?orgnr=' + orgnr + '">View record ↗</a></article>'
        )
    return '<section class="result"><div class="section-kicker">REGISTRY SEARCH RESULTS</div><h2>Matches for “' + html.escape(query) + '”</h2><p class="muted">' + str(len(results)) + ' result(s) returned. Confirm the correct legal entity before continuing.</p>' + "".join(cards) + '<div class="result-actions"><a class="button secondary" href="/">↺ New search</a></div></section>'


@app.get("/", response_class=HTMLResponse)
def home(orgnr: str = Query(default="", max_length=30), q: str = Query(default="", max_length=120)):
    result_html = ""
    error_message = ""
    search_text = q.strip()
    direct_orgnr = orgnr.strip() or (search_text if re.fullmatch(r"\\d{9}", re.sub(r"\\s+", "", search_text)) else "")
    if direct_orgnr:
        try:
            result_html = _company_result(lookup_company(direct_orgnr))
        except (ValueError, LookupError, RuntimeError) as exc:
            error_message = str(exc)
    elif search_text:
        try:
            result_html = _search_results(search_text, search_companies(search_text))
        except (ValueError, LookupError, RuntimeError) as exc:
            error_message = str(exc)

    if error_message:
        result_html = '<section class="error"><strong>Could not complete search</strong><p>' + html.escape(error_message) + '</p><a class="button secondary" href="/">↺ Reset and try again</a></section>'

    return HTMLResponse(
        """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101827">
<meta name="description" content="Search Norwegian organisations and verify company details against the official Brønnøysund Register.">
<title>Signalpost — Company Intelligence</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23101827'/%3E%3Cpath d='M15 44V20h8l18 15V20h8v24h-8L23 29v15z' fill='%237ce8c2'/%3E%3C/svg%3E">
<style>
:root{color-scheme:dark;--bg:#0b1120;--panel:#131e31;--panel2:#17243a;--line:#2a3b53;--muted:#a7b6cc;--ink:#f3f7ff;--mint:#7ce8c2;--blue:#8ab9ff}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 15% -5%,#17444a 0,transparent 38%),radial-gradient(ellipse at 100% 20%,#1b2a4b 0,transparent 32%),var(--bg);color:var(--ink);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:26px 22px 60px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #ffffff12;padding:8px 0 20px}.brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--ink)}.logo{width:44px;height:44px;display:grid;place-items:center;background:#132b34;border:1px solid #346357;border-radius:14px;flex-shrink:0}.brand-name{font-weight:850;letter-spacing:2px;font-size:15px}.brand-sub{display:block;font-size:11px;color:var(--muted);letter-spacing:.8px}.status{font-size:11px;letter-spacing:1px;font-weight:800;color:var(--mint);border:1px solid #2b6556;background:#102b29;border-radius:999px;padding:6px 10px}
.hero{padding:55px 0 28px}.kicker,.section-kicker{font-size:11px;letter-spacing:2px;font-weight:850;color:var(--mint)}h1{font-size:clamp(38px,7vw,68px);line-height:1.02;letter-spacing:-2.7px;margin:15px 0 20px;max-width:780px}.hero p{color:var(--muted);max-width:660px;font-size:17px}.hero strong{color:var(--ink)}
.panel,.result{border:1px solid var(--line);border-radius:22px;background:linear-gradient(145deg,#17253aee,#111b2dee);padding:26px;margin:20px 0;box-shadow:0 18px 55px #00000018}.search-label{display:block;font-weight:750;margin-bottom:12px;font-size:14px}.search-row{display:flex;gap:10px;flex-wrap:wrap}.search-input{flex:1;min-width:220px;width:100%;padding:15px 16px;border:1px solid #40536d;border-radius:12px;background:#0b1424;color:white;font:inherit;outline:none}.search-input:focus{border-color:var(--mint);box-shadow:0 0 0 3px #7ce8c21b}.button{display:inline-flex;justify-content:center;align-items:center;gap:8px;padding:13px 18px;border:1px solid transparent;border-radius:12px;background:var(--mint);color:#08211a;text-decoration:none;font-weight:850;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}.button:hover{filter:brightness(1.06);transform:translateY(-1px)}.button.secondary{background:#1b2b42;border-color:#3b506c;color:var(--ink)}.button.small{padding:10px 13px;font-size:13px}.hint,.muted{font-size:13px;color:var(--muted)}.hint{margin:13px 0 0}.result h2{font-size:clamp(23px,4vw,32px);line-height:1.2;letter-spacing:-.8px;margin:10px 0 16px;overflow-wrap:anywhere}.result table{width:100%;border-collapse:collapse;margin:20px 0}.result th,.result td{text-align:left;padding:13px 8px;border-bottom:1px solid #ffffff12;vertical-align:top;overflow-wrap:anywhere}.result th{color:var(--muted);width:34%;font-weight:550}.result td{font-weight:600}.source-link{color:var(--mint);font-weight:750;text-decoration:none}.result-actions{margin-top:22px;padding-top:18px;border-top:1px solid #ffffff12}.error{padding:20px;border:1px solid #9b5a6c;background:#351f2c;border-radius:16px;margin:20px 0}.error p{color:#e9c7d0}.match{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 0;border-bottom:1px solid #ffffff14}.match:last-of-type{border-bottom:0}.match h3{margin:3px 0;font-size:19px;overflow-wrap:anywhere}.match-type{font-size:11px;color:var(--mint);text-transform:uppercase;letter-spacing:1px;font-weight:800}.match p{margin:3px 0;overflow-wrap:anywhere}.footer{border-top:1px solid #ffffff14;margin-top:35px;padding-top:22px;color:var(--muted);font-size:12px}.footer a{color:var(--mint)}.purpose{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.purpose article{padding:17px;border:1px solid #ffffff12;border-radius:15px;background:#ffffff04}.purpose b{display:block;font-size:14px;margin-bottom:5px}.purpose p{font-size:13px;color:var(--muted);margin:0}.purpose-icon{font-size:20px;margin-bottom:8px}
@media(max-width:640px){main{padding:18px 14px 40px}.hero{padding:39px 0 20px}h1{letter-spacing:-1.7px}.panel,.result{padding:18px;border-radius:17px}.search-row .button{width:100%}.match{align-items:flex-start;flex-direction:column;gap:12px}.match .button{width:100%}.result th{width:40%;padding-right:10px}.result th,.result td{font-size:13px;padding:11px 5px}.purpose{grid-template-columns:1fr}.status{font-size:9px}.topbar{align-items:flex-start}}
</style>
</head>
<body><main>
<nav class="topbar"><a class="brand" href="/" aria-label="Signalpost home"><span class="logo"><svg width="27" height="27" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 24V8h5l12 10V8h5v16h-5L10 14v10z" fill="#7ce8c2"/><path d="M4 28h24" stroke="#8ab9ff" stroke-width="2" stroke-linecap="round"/></svg></span><span><span class="brand-name">SIGNALPOST</span><span class="brand-sub">COMPANY INTELLIGENCE</span></span></a><span class="status">● LIVE PROTOTYPE</span></nav>
<header class="hero"><div class="kicker">NORWEGIAN COMPANY RESEARCH</div><h1>Know the company.<br>Verify the evidence.</h1><p>Find a registered Norwegian organisation by <strong>company name or organisation number</strong>. Start with the official register, then follow the source for yourself.</p></header>
<section class="panel"><form method="get" action="/" id="search-form"><label class="search-label" for="search-query">What company are you looking for?</label><div class="search-row"><input class="search-input" id="search-query" name="q" value="""" + html.escape(q, quote=True) + """" placeholder="Company name or 9-digit organisation number" autocomplete="off" aria-describedby="search-hint" required><button class="button" type="submit">Search registry ↗</button></div><p class="hint" id="search-hint">Tip: enter a company name if you don’t know its organisation number. Search uses the official Brønnøysund Register.</p></form></section>
""" + result_html + """
<section class="panel"><div class="section-kicker">WHY SIGNALPOST</div><h2>Research you can trace back to its source.</h2><div class="purpose"><article><div class="purpose-icon">⌕</div><b>Find the right entity</b><p>Search by name or number and check the legal organisation before relying on its details.</p></article><article><div class="purpose-icon">↗</div><b>Verify the source</b><p>Open the original public registry record instead of treating an unlinked claim as fact.</p></article><article><div class="purpose-icon">◎</div><b>Start due diligence</b><p>Use official identity details as a starting point for supplier, customer, or partner research.</p></article></div><p class="hint">This public prototype currently provides official-registry search and lookup. It is not the full batch research pipeline and does not independently verify every financial, social, or news claim.</p><p class="hint">Source: <a class="source-link" href="https://www.brreg.no/en/" target="_blank" rel="noopener noreferrer">Brønnøysund Register Centre</a> · <a class="source-link" href="/docs">API documentation ↗</a> · <a class="source-link" href="/healthz">Service health ↗</a></p></section>
<footer class="footer">Signalpost Company Intelligence · Prototype · Registry data may be incomplete or change over time. <a href="https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html" target="_blank" rel="noopener noreferrer">Registry API documentation</a></footer>
</main><script>
(function(){const input=document.getElementById('search-query');if(!input)return;input.addEventListener('keydown',function(e){if(e.key==='Escape'){input.value='';input.focus();}});})();
</script></body></html>"""
    )
