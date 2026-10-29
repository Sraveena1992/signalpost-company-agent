from __future__ import annotations

import html
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Signalpost Company Intelligence",
    description="Evidence-linked Norwegian company lookup using the official Brønnøysund Register API.",
    version="1.1.0",
)

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger("signalpost")
REGISTRY_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/"
REGISTRY_SEARCH_URL = REGISTRY_URL
# Bound expensive on-demand research so a burst of requests cannot spawn unlimited workers.
_RESEARCH_SLOTS = threading.BoundedSemaphore(value=2)
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMITS: dict[str, deque[float]] = {}
_RESEARCH_RATE_LIMIT = 5
_RESEARCH_RATE_WINDOW_SECONDS = 60


def _research_rate_limited(client_host: str, now: float | None = None) -> bool:
    """Simple per-client fixed-window limiter; concurrency is separately bounded."""
    current = time.monotonic() if now is None else now
    with _RATE_LIMIT_LOCK:
        requests = _RATE_LIMITS.setdefault(client_host or "unknown", deque())
        while requests and current - requests[0] >= _RESEARCH_RATE_WINDOW_SECONDS:
            requests.popleft()
        if len(requests) >= _RESEARCH_RATE_LIMIT:
            return True
        requests.append(current)
        if len(_RATE_LIMITS) > 256:
            # Bound memory used by client buckets under random-source traffic.
            oldest_key = next(iter(_RATE_LIMITS))
            if oldest_key != (client_host or "unknown"):
                _RATE_LIMITS.pop(oldest_key, None)
        return False


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.url.path == "/" and response.headers.get("content-type", "").startswith("text/html"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' data:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
    return response


def _get_json(url: str) -> dict:
    request = URLRequest(
        url,
        headers={
            "Accept": "application/vnd.brreg.enhetsregisteret.enhet.v2+json, application/json;q=0.9",
            "User-Agent": "SignalpostCompanyAgent/1.2",
        },
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


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

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


@app.get("/api/research/{orgnr}")
def research_api(orgnr: str, request: Request):
    """Run the actual evidence-rich single-company batch pipeline on demand."""
    client_host = request.client.host if request.client else "unknown"
    if _research_rate_limited(client_host):
        return JSONResponse(status_code=429, content={"error": "Research rate limit reached. Please wait a minute before trying again."})
    try:
        company = lookup_company(orgnr)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except LookupError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

    run_id = "web-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="signalpost-research-") as temporary:
        work = Path(temporary)
        inputs = work / "organisations.json"
        terminal_path = work / "terminal.jsonl"
        profiles_path = work / "profiles.jsonl"
        report_path = work / "report.json"
        inputs.write_text(json.dumps([company["organisation_number"]]), encoding="utf-8")
        command = [
            sys.executable, str(ROOT / "scripts" / "run_competition_batch.py"),
            "--organisations", str(inputs),
            "--output", str(terminal_path),
            "--profiles-output", str(profiles_path),
            "--report", str(report_path),
            "--run-id", run_id,
            "--expected-count", "1",
            "--workers", "1",
            "--checkpoint-every", "1",
        ]
        if not _RESEARCH_SLOTS.acquire(blocking=False):
            return JSONResponse(status_code=429, content={"error": "Research capacity is busy. Please retry in a minute."})
        try:
            try:
                completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=150, check=False, env={**os.environ, "PYTHONUNBUFFERED": "1"})
            except subprocess.TimeoutExpired:
                return JSONResponse(status_code=504, content={"error": "Research exceeded the 150-second limit. Try again later."})
        finally:
            _RESEARCH_SLOTS.release()
        if completed.returncode != 0:
            # Keep internal tracebacks and filesystem details in server logs, not public API responses.
            logger.error(
                "Research pipeline failed run_id=%s diagnostic=%s",
                run_id,
                (completed.stderr or completed.stdout or "No diagnostic output")[-1200:],
            )
            return JSONResponse(status_code=502, content={"error": "The research pipeline did not complete successfully. Please retry later or contact the project owner with the run ID.", "run_id": run_id})
        try:
            profiles = [json.loads(line) for line in profiles_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            terminals = [json.loads(line) for line in terminal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return JSONResponse(status_code=502, content={"error": "Research finished but its output could not be read.", "run_id": run_id, "detail": type(exc).__name__})
        if len(profiles) != 1 or len(terminals) != 1:
            return JSONResponse(status_code=502, content={"error": "Research output did not contain exactly one company.", "run_id": run_id})
        return {"company": company, "run_id": run_id, "terminal": terminals[0], "profile": profiles[0], "report": report, "scope_note": "This runs the real implemented batch modules. It does not include an external jobs connector or guarantee a Builderr score."}


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
        '<div class="result-actions"><button class="button" type="button" id="run-research" data-orgnr="' + html.escape(str(company.get("organisation_number") or ""), quote=True) + '">Run evidence research ↗</button> <a class="button secondary" href="/">↺ New search</a><p class="hint">Runs the real research pipeline for this company. It may take up to 150 seconds.</p><div id="research-output" aria-live="polite"></div></div></section>'
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
def home(orgnr: str = "", q: str = ""):
    # Plain Python defaults avoid leaking FastAPI Query objects when this view is
    # invoked directly by tests or internal callers. Validate again at the boundary.
    orgnr = str(orgnr or "").strip()[:30]
    q = str(q or "").strip()[:120]
    result_html = ""
    error_message = ""
    search_text = q
    direct_orgnr = orgnr.strip() or (search_text if re.fullmatch(r"\d{9}", re.sub(r"\s+", "", search_text)) else "")
    if direct_orgnr:
        try:
            result_html = _company_result(lookup_company(direct_orgnr))
        except (ValueError, LookupError, RuntimeError) as exc:
            error_message = str(exc)
        except Exception:
            logger.exception("Unexpected company lookup error")
            error_message = "The company lookup could not be completed. Please retry later."
    elif search_text:
        try:
            result_html = _search_results(search_text, search_companies(search_text))
        except (ValueError, LookupError, RuntimeError) as exc:
            error_message = str(exc)
        except Exception:
            logger.exception("Unexpected company search error")
            error_message = "The company search could not be completed. Please retry later."

    if error_message:
        result_html = '<section class="error"><strong>Could not complete search</strong><p>' + html.escape(error_message) + '</p><a class="button secondary" href="/">↺ Reset and try again</a></section>'

    html_page = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101827">
<meta name="description" content="Search Norwegian organisations and verify company details against the official Brønnøysund Register.">
<title>Signalpost — Company Intelligence</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23101827'/%3E%3Cpath d='M15 44V20h8l18 15V20h8v24h-8L23 29v15z' fill='%2367dec7'/%3E%3C/svg%3E">
<style>
:root{color-scheme:dark;--bg:#101827;--panel:#192638;--panel2:#223349;--line:#3b4c62;--muted:#bdc9d8;--ink:#f7f8fb;--mint:#67dec7;--blue:#f2bd78}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 15% -5%,#173e43 0,transparent 38%),radial-gradient(ellipse at 100% 20%,#29334d 0,transparent 32%),var(--bg);color:var(--ink);font:16px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:26px 22px 60px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid #ffffff12;padding:8px 0 20px}.brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:var(--ink)}.logo{width:44px;height:44px;display:grid;place-items:center;background:#1c3a40;border:1px solid #3d8176;border-radius:14px;flex-shrink:0}.brand-name{font-weight:850;letter-spacing:2px;font-size:15px}.brand-sub{display:block;font-size:11px;color:var(--muted);letter-spacing:.8px}.status{font-size:11px;letter-spacing:1px;font-weight:800;color:var(--mint);border:1px solid #357c70;background:#153733;border-radius:999px;padding:6px 10px}
.hero{padding:55px 0 28px}.kicker,.section-kicker{font-size:11px;letter-spacing:2px;font-weight:850;color:var(--mint)}h1{font-size:clamp(38px,7vw,68px);line-height:1.02;letter-spacing:-2.7px;margin:15px 0 20px;max-width:780px}.hero p{color:var(--muted);max-width:660px;font-size:17px}.hero strong{color:var(--ink)}
.panel,.result{border:1px solid var(--line);border-radius:22px;background:linear-gradient(145deg,#1d2b3fee,#152233ee);padding:26px;margin:20px 0;box-shadow:0 18px 55px #00000018}.search-label{display:block;font-weight:750;margin-bottom:12px;font-size:14px}.search-row{display:flex;gap:10px;flex-wrap:wrap}.search-input{flex:1;min-width:220px;width:100%;padding:15px 16px;border:1px solid #53657d;border-radius:12px;background:#121e2e;color:white;font:inherit;outline:none}.search-input:focus{border-color:var(--mint);box-shadow:0 0 0 3px #67dec71b}.button{display:inline-flex;justify-content:center;align-items:center;gap:8px;padding:13px 18px;border:1px solid transparent;border-radius:12px;background:var(--mint);color:#09231f;text-decoration:none;font-weight:850;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}.button:hover{filter:brightness(1.06);transform:translateY(-1px)}.button.secondary{background:#29384d;border-color:#4b5e76;color:var(--ink)}.button.small{padding:10px 13px;font-size:13px}.hint,.muted{font-size:13px;color:var(--muted)}.hint{margin:13px 0 0}.result h2{font-size:clamp(23px,4vw,32px);line-height:1.2;letter-spacing:-.8px;margin:10px 0 16px;overflow-wrap:anywhere}.result table{width:100%;border-collapse:collapse;margin:20px 0}.result th,.result td{text-align:left;padding:13px 8px;border-bottom:1px solid #ffffff12;vertical-align:top;overflow-wrap:anywhere}.result th{color:var(--muted);width:34%;font-weight:550}.result td{font-weight:600}.source-link{color:var(--mint);font-weight:750;text-decoration:none}.result-actions{margin-top:22px;padding-top:18px;border-top:1px solid #ffffff12}.error{padding:20px;border:1px solid #9b5a6c;background:#351f2c;border-radius:16px;margin:20px 0}.error p{color:#e9c7d0}.match{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 0;border-bottom:1px solid #ffffff14}.match:last-of-type{border-bottom:0}.match h3{margin:3px 0;font-size:19px;overflow-wrap:anywhere}.match-type{font-size:11px;color:var(--mint);text-transform:uppercase;letter-spacing:1px;font-weight:800}.match p{margin:3px 0;overflow-wrap:anywhere}.footer{border-top:1px solid #ffffff14;margin-top:35px;padding-top:22px;color:var(--muted);font-size:12px}.footer a{color:var(--mint)}.purpose{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.purpose article{padding:17px;border:1px solid #ffffff12;border-radius:15px;background:#ffffff04}.purpose b{display:block;font-size:14px;margin-bottom:5px}.purpose p{font-size:13px;color:var(--muted);margin:0}.purpose-icon{font-size:20px;margin-bottom:8px}
/* Keep evidence output inside its card/viewport, including long source URLs and nested JSON. */
.result{min-width:0;max-width:100%;overflow:hidden}
.result table{width:100%;max-width:100%;table-layout:fixed;display:block;overflow-x:auto}
.result th,.result td{min-width:0;overflow-wrap:anywhere;word-break:break-word}
/* Keep evidence source links readable instead of wrapping one character per line. */
.result .facts-table{display:table;table-layout:auto;overflow:visible;border-collapse:collapse}
.result .facts-table th:first-child{width:24%}
.result .facts-table td:nth-child(2){width:48%}
.result .facts-table th:last-child,.result .facts-table td:last-child{width:120px;min-width:120px;white-space:nowrap;overflow-wrap:normal;word-break:normal}
.result .facts-table .source-link{white-space:nowrap;word-break:normal;overflow-wrap:normal}
.evidence-grid{grid-template-columns:repeat(2,minmax(0,1fr));min-width:0}
.article-evidence{min-width:0;max-width:100%;overflow:hidden;overflow-wrap:anywhere}
.article-evidence .source-link{overflow-wrap:anywhere;word-break:break-all}
.article-evidence pre,.result pre{max-width:100%;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;overflow-x:auto}
.article-evidence details,.result details{min-width:0;max-width:100%}
@media(max-width:640px){.evidence-grid{grid-template-columns:minmax(0,1fr)}.result table{font-size:12px}.result th,.result td{padding:9px 6px}}
@media(max-width:640px){main{padding:18px 14px 40px}.hero{padding:39px 0 20px}h1{letter-spacing:-1.7px}.panel,.result{padding:18px;border-radius:17px}.search-row .button{width:100%}.match{align-items:flex-start;flex-direction:column;gap:12px}.match .button{width:100%}.result th{width:40%;padding-right:10px}.result th,.result td{font-size:13px;padding:11px 5px}.purpose{grid-template-columns:1fr}.status{font-size:9px}.topbar{align-items:flex-start}}

/* Premium light theme: calmer surfaces, stronger contrast, and less visual weight. */
:root{color-scheme:light;--bg:#f3f6fb;--panel:#ffffff;--panel2:#f8fafc;--line:#dce4ee;--muted:#58677c;--ink:#152238;--mint:#087f78;--blue:#b77927}
body{background:radial-gradient(ellipse at 8% 0%,#d9f2ee 0,transparent 34%),radial-gradient(ellipse at 100% 8%,#e6edff 0,transparent 34%),var(--bg);color:var(--ink)}
.topbar{border-bottom:1px solid #dbe4ee}
.logo{background:#e0f5f1;border-color:#a8dcd4}
.status{color:#087f78;border-color:#b7e3dc;background:#e5f7f3}
.kicker,.section-kicker,.match-type{color:#087f78}
.hero p,.brand-sub,.hint,.muted{color:#58677c}
.hero strong{color:#152238}
.panel,.result{background:rgba(255,255,255,.92);border-color:#dce4ee;box-shadow:0 12px 32px rgba(24,44,76,.07)}
.search-input{background:#f8fafc;border-color:#cbd6e3;color:#152238}
.search-input::placeholder{color:#748197}
.search-input:focus{border-color:#0b958b;box-shadow:0 0 0 3px rgba(11,149,139,.13)}
.button{background:#0b958b;color:#fff;font-weight:750}
.button:hover{filter:brightness(.97)}
.button.secondary{background:#fff;border-color:#cbd6e3;color:#25364f}
.result th,.result td{border-bottom-color:#e6ebf2}
.result-actions,.footer{border-top-color:#e2e8f0}
.purpose article{background:#f8fafc;border-color:#e2e8f0}
.error{background:#fff1f2;border-color:#fecdd3;color:#881337}
.error p{color:#9f1239}
.source-link,.footer a{color:#087f78}
.result .facts-table .source-link{color:#087f78}
@media(prefers-reduced-motion:no-preference){.panel,.result{transition:box-shadow .18s ease,border-color .18s ease}.panel:hover,.result:hover{box-shadow:0 16px 38px rgba(24,44,76,.09);border-color:#c8d5e4}}
</style>
</head>
<body><main>
<nav class="topbar"><a class="brand" href="/" aria-label="Signalpost home"><span class="logo"><svg width="27" height="27" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M5 24V8h5l12 10V8h5v16h-5L10 14v10z" fill="#67dec7"/><path d="M4 28h24" stroke="#f2bd78" stroke-width="2" stroke-linecap="round"/></svg></span><span><span class="brand-name">SIGNALPOST</span><span class="brand-sub">COMPANY INTELLIGENCE</span></span></a><span class="status">● LIVE PROTOTYPE</span></nav>
<header class="hero"><div class="kicker">NORWEGIAN COMPANY RESEARCH</div><h1>Know the company.<br>Verify the evidence.</h1><p>Find a registered Norwegian organisation by <strong>company name or organisation number</strong>. Start with the official register, then follow the source for yourself.</p></header>
<section class="panel"><form method="get" action="/" id="search-form"><label class="search-label" for="search-query">What company are you looking for?</label><div class="search-row"><input class="search-input" id="search-query" name="q" value="__SEARCH_VALUE__" placeholder="Company name or 9-digit organisation number" autocomplete="off" aria-describedby="search-hint" required><button class="button" type="submit">Search registry ↗</button></div><p class="hint" id="search-hint">Tip: enter a company name if you don’t know its organisation number. Search uses the official Brønnøysund Register.</p></form></section>
""" + result_html + """
<section class="panel"><div class="section-kicker">WHY SIGNALPOST</div><h2>Research you can trace back to its source.</h2><div class="purpose"><article><div class="purpose-icon">⌕</div><b>Find the right entity</b><p>Search by name or number and check the legal organisation before relying on its details.</p></article><article><div class="purpose-icon">↗</div><b>Verify the source</b><p>Open the original public registry record instead of treating an unlinked claim as fact.</p></article><article><div class="purpose-icon">◎</div><b>Start due diligence</b><p>Use official identity details as a starting point for supplier, customer, or partner research.</p></article></div><p class="hint">Select a company and use “Run evidence research” to inspect implemented research modules, source-linked facts, and the run report. The public app researches one company per run; it is not a hosted 100-company dashboard and does not independently verify every financial, social, or news claim.</p><p class="hint">Source: <a class="source-link" href="https://www.brreg.no/en/" target="_blank" rel="noopener noreferrer">Brønnøysund Register Centre</a> · <a class="source-link" href="/docs">API documentation ↗</a> · <a class="source-link" href="/healthz">Service health ↗</a></p></section>
<footer class="footer">Signalpost Company Intelligence · Prototype · Registry data may be incomplete or change over time. <a href="https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html" target="_blank" rel="noopener noreferrer">Registry API documentation</a></footer>
</main><script>
(function(){
const input=document.getElementById('search-query');
if(input)input.addEventListener('keydown',function(e){if(e.key==='Escape'){input.value='';input.focus();}});
const button=document.getElementById('run-research'),output=document.getElementById('research-output');
if(!button||!output)return;
button.addEventListener('click',async function(){
button.disabled=true;button.textContent='Research running…';output.innerHTML='<p class="hint">Checking registry, accounting, financials, roles, group/location and verified company-site evidence. Keep this page open.</p>';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
try{
const response=await fetch('/api/research/'+encodeURIComponent(button.dataset.orgnr)),data=await response.json();
if(!response.ok)throw new Error(data.error||'Research failed');
const profile=data.profile||{},evidence=profile.evidence||{},synthesis=profile.synthesis||{};
let cards='',facts='';
for(const [key,item] of Object.entries(evidence)){
const value=item.value;
cards+='<article class="purpose article-evidence"><div class="match-type">'+esc(key.replaceAll('_',' '))+' · '+esc(item.status)+'</div><p>'+esc(item.note||'Evidence captured for this module.')+'</p><p class="hint">Source: '+(item.source_url?'<a class="source-link" target="_blank" rel="noopener noreferrer" href="'+esc(item.source_url)+'">'+esc(item.source_url)+'</a>':'not provided')+'</p><details><summary>Inspect returned data</summary><pre>'+esc(JSON.stringify(value??null,null,2))+'</pre></details></article>';
}
const displayValue=value=>value===null||value===undefined?'—':(typeof value==='object'?JSON.stringify(value):String(value));
for(const fact of (synthesis.facts||[]))facts+='<tr><th>'+esc(fact.claim)+'</th><td>'+esc(displayValue(fact.value))+'</td><td>'+(fact.source_url?'<a class="source-link" target="_blank" rel="noopener noreferrer" href="'+esc(fact.source_url)+'">Source ↗</a>':'Source unavailable')+'</td></tr>';
const factCount=(synthesis.facts||[]).length, availableModules=Object.values(evidence).filter(item=>item.status==='available').length;
const overview=synthesis.summary||('Research returned '+factCount+' source-linked facts across '+availableModules+' available evidence modules. Open each module below to inspect source records and uncertainty notes.');
output.innerHTML='<section class="result"><div class="section-kicker">EVIDENCE RESEARCH RESULT</div><h2>'+esc(profile.name||data.company?.name)+'</h2><p class="hint">Run '+esc(data.run_id)+' · '+esc(data.terminal?.terminal_state||data.terminal?.status||'Completed')+'</p><h3>Source-linked synthesis</h3><p>'+esc(overview)+'</p><p class="hint">Baseline: '+esc(synthesis.change_status||'not stated')+' · Facts: '+esc(factCount)+' · Unsupported/uncertain: '+esc((synthesis.unsupported_or_uncertain||[]).length)+'</p>'+(facts?'<table class="facts-table">'+facts+'</table>':'')+'<h3>Module evidence</h3><div class="purpose evidence-grid">'+cards+'</div><details><summary>Run report and terminal envelope</summary><pre>'+esc(JSON.stringify({terminal:data.terminal,report:data.report,unsupported_or_uncertain:synthesis.unsupported_or_uncertain,changes:profile.changes},null,2))+'</pre></details><p class="hint">'+esc(data.scope_note)+'</p></section>';
}catch(error){output.innerHTML='<section class="error"><strong>Research could not be completed</strong><p>'+esc(error.message)+'</p></section>';}
finally{button.disabled=false;button.textContent='Run evidence research ↗';}
});
})();
</script><script src="/static/signalpost_dashboard.js" defer></script></body></html>"""
    html_page = html_page.replace("__SEARCH_VALUE__", html.escape(q, quote=True))
    return HTMLResponse(html_page)
