import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

"""Regressions from the 13 November Builderr evaluator feedback."""
from norway_company_agent.identity import apply_website_identity_gate, assess_social_identity
from norway_company_agent.research import answer_profile
from scripts.extract_company_site_news import observation as news_observation


def test_squarespace_social_links_not_attributed_to_lovehjerte_design():
    profile = {"organisation_number": "999999991", "name": "LØWEHJERTE DESIGN AS", "evidence": {}}
    website = {
        "status": "available",
        "source_url": "https://lovehjertedesign.squarespace.com/",
        "value": {
            "final_url": "https://lovehjertedesign.squarespace.com/",
            "title": "LØWEHJERTE DESIGN AS",
            "main_text_excerpt": "LØWEHJERTE DESIGN AS designer products. " * 8,
            "social_links": [
                {"platform": "x", "url": "https://x.com/squarespace"},
                {"platform": "linkedin", "url": "https://linkedin.com/company/squarespace"},
            ],
        },
    }
    result = apply_website_identity_gate(profile, website)
    assert result["website"]["value"]["social_links"] == []
    assert result["quarantined_social_links"] == 2


def test_squarespace_handle_rejected_for_different_company():
    profile = {"name": "LØWEHJERTE DESIGN AS", "organisation_number": "999999991"}
    assert not assess_social_identity(profile, {"platform": "x", "url": "https://x.com/squarespace"})["publishable"]
    assert not assess_social_identity(profile, {"platform": "linkedin", "url": "https://linkedin.com/company/squarespace"})["publishable"]


def test_missing_explicit_website_gate_cannot_publish_claims():
    profile = {
        "organisation_number": "999999991",
        "name": "LØWEHJERTE DESIGN AS",
        "evidence": {"website": {
            "status": "available",
            "source_url": "https://www.example.com/",
            "value": {
                "description": "Unverified marketing copy",
                "social_links": [{"platform": "x", "url": "https://x.com/squarespace"}],
            },
        }},
    }
    facts = answer_profile(profile, "Give me a company overview")["facts"]
    assert not any(f["classification"] in {"company_reported_claim", "company_linked_social_profile"} for f in facts)


def test_verified_company_news_needs_date_and_exact_company_attribution():
    import hashlib
    source = "https://www.example.no/news/new-project"
    profile = {
        "organisation_number": "999999991",
        "name": "EXAMPLE AS",
        "evidence": {
            "website": {
                "status": "available", "source_url": "https://www.example.no/",
                "retrieved_at": "2026-11-13T00:00:00Z",
                "value": {
                    "identity_assessment": {"publishable": True, "score": 1.0},
                    "pages": [{
                        "url": source,
                        "title": "EXAMPLE opens new research centre",
                        "published_at": "2026-11-12",
                        "article_like": True,
                        "main_text_excerpt": "The company opened a new research centre today. " * 5,
                        "content_sha256": hashlib.sha256(b"article").hexdigest(),
                    }],
                },
            },
        },
    }
    item = news_observation(profile)
    assert item and item["source_url"] == source and item["published_at"] == "2026-11-12"
    profile["evidence"]["website"]["value"]["pages"][0]["published_at"] = None
    assert news_observation(profile) is None
    profile["evidence"]["website"]["value"]["pages"][0]["published_at"] = "2026-11-12"
    profile["evidence"]["website"]["value"]["pages"][0]["url"] = "https://unrelated-vendor.no/news/new-project"
    assert news_observation(profile) is None
    profile["evidence"]["website"]["value"]["pages"][0]["url"] = source
    profile["evidence"]["website"]["value"]["pages"][0]["published_at"] = "2099-01-01"
    assert news_observation(profile) is None


def test_company_owned_jobposting_requires_date_exact_company_and_source():
    import hashlib
    from datetime import timedelta, datetime, timezone
    from scripts.extract_company_site_jobs import observation as job_observation
    url = "https://example.no/careers/backend-developer"
    item = {
        "title": "Backend Developer",
        "datePosted": "2026-11-12",
        "validThrough": (datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat(),
        "hiringOrganization": {"name": "EXAMPLE AS"},
        "url": url,
    }
    profile = {
        "name": "EXAMPLE AS",
        "organisation_number": "999999991",
        "evidence": {"website": {
            "status": "available", "source_url": "https://example.no",
            "retrieved_at": "2026-11-13",
            "value": {
                "final_url": "https://example.no",
                "identity_assessment": {"publishable": True, "score": 1.0},
                "pages": [{"url": url, "content_sha256": hashlib.sha256(b"job").hexdigest(), "job_postings": [item]}],
            },
        }},
    }
    result = job_observation(profile)
    assert result and result["signal_type"] == "job_posting"
    assert result["source_url"] == url
    item["hiringOrganization"] = {"name": "SQUARESPACE"}
    assert job_observation(profile) is None
    item["hiringOrganization"] = {"name": "EXAMPLE AS"}
    item["url"] = "https://squarespace.com/jobs/backend"
    assert job_observation(profile) is None


def test_synthesis_reports_verified_business_and_honest_unknowns():
    from norway_company_agent.batch import attach_synthesis
    profile = {
        "organisation_number": "999999991",
        "name": "EXAMPLE AS",
        "industry": {"beskrivelse": "Computer programming"},
        "evidence": {
            "registry_live": {
                "status": "available",
                "value": {"name": "EXAMPLE AS"},
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/999999991",
                "retrieved_at": "2026-11-13T00:00:00Z",
            },
            "financials": {"status": "not_found"},
            "website": {"status": "ambiguous"},
        },
    }
    attach_synthesis(profile)
    overview = profile["synthesis"]["overview"]
    assert any("Computer programming" in entry["text"] for entry in overview)
    assert all(entry["source_url"] and entry["retrieved_at"] for entry in overview)
    assert profile["synthesis"]["what_changed"]["status"] == "no_previous_snapshot"
    assert any(item["topic"] == "normalized annual accounts" for item in profile["synthesis"]["unknowns"])


def test_real_registry_directory_bounded_two_pages(monkeypatch):
    import app
    calls = []
    def fake_get(url):
        calls.append(url)
        return {"_embedded": {"enheter": [{
            "organisasjonsnummer": "923609016",
            "navn": "EQUINOR ASA",
            "organisasjonsform": {"beskrivelse": "Allmennaksjeselskap"},
            "forretningsadresse": {"adresse": ["Forusbeen 50"], "postnummer": "4035", "poststed": "STAVANGER"},
            "naeringskode1": {"beskrivelse": "Utvinning av råolje"},
        }]}}
    monkeypatch.setattr(app, "_get_json", fake_get)
    result = app.browse_registry_page(page=1, size=100)
    assert result["results"][0]["organisation_number"] == "923609016"
    assert result["results"][0]["registry_source"].endswith("/923609016")
    assert "page=1" in calls[0] and "size=100" in calls[0]
    import pytest
    with pytest.raises(ValueError):
        app.browse_registry_page(page=3)


def test_workspace_exposes_live_company_directory():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "intelligence.html").read_text(encoding="utf-8")
    assert 'id="browseDirectory"' in html
    assert '/api/directory?page=' in html
    assert 'id="filterDirectory"' in html
    assert 'id="sortDirectory"' in html
    assert 'addSuggestions(directoryRows)' in html


def test_social_handle_match_alone_does_not_prove_account_ownership():
    profile={"organisation_number":"923609016","name":"EQUINOR ASA"}
    website={"status":"available","source_url":"https://www.equinor.com","value":{
        "final_url":"https://www.equinor.com",
        "title":"EQUINOR ASA",
        "description":"EQUINOR ASA global energy organisation.",
        "main_text_excerpt":"EQUINOR ASA global energy organisation. "*10,
        "social_links":[{"platform":"x","url":"https://x.com/equinor"}]}}
    assessment=apply_website_identity_gate(profile,website)
    assert assessment["assessment"]["publishable"] is True
    assert assessment["website"]["value"]["social_links"] == []
    assert assessment["quarantined_social_links"] == 1


def test_directory_supports_300_real_registry_entries_and_auto_discovery():
    import app
    import inspect
    assert "0 <= page <= 2" in inspect.getsource(app.browse_registry_page)
    source=(ROOT/"static"/"intelligence.html").read_text(encoding="utf-8")
    assert "for(let page=0;page<3;page++)" in source
    assert "await loadDirectory(false)" in source
    assert "Browse 300 Norwegian registry companies" in source


def test_synthesis_includes_exact_owned_company_news_and_jobs_only():
    from datetime import date
    from norway_company_agent.research import answer_profile
    site = "https://example-company.no"
    org = "999999991"
    base = {
        "organisation_number": org, "name": "EXAMPLE COMPANY AS",
        "evidence": {
            "registry": {"status": "available", "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/999999991", "retrieved_at": "2026-11-13T00:00:00Z"},
            "website": {"status": "available", "source_url": site, "value": {
                "final_url": site, "identity_assessment": {"publishable": True}}},
            "public_activity": {"status": "available", "retrieved_at": "2026-11-13T00:00:00Z", "value": {
                "observations": [
                    {"organisation_number": org, "signal_type": "public_post",
                     "exact_entity": True, "source_url": site+"/news/launch",
                     "published_at": date.today().isoformat(), "rights_status": "approved",
                     "retrieved_at": "2026-11-13T00:00:00Z",
                     "content_sha256": "a"*64, "evidence_span": "EXAMPLE COMPANY AS announces a launch"},
                    {"organisation_number": org, "signal_type": "job_posting",
                     "exact_entity": True, "source_url": site+"/careers/engineer",
                     "published_at": date.today().isoformat(), "rights_status": "approved",
                     "retrieved_at": "2026-11-13T00:00:00Z",
                     "content_sha256": "b"*64, "evidence_span": "EXAMPLE COMPANY AS hiring engineer"},
                    {"organisation_number": "111111111", "signal_type": "public_post",
                     "exact_entity": True, "source_url": site+"/news/other",
                     "published_at": date.today().isoformat(), "rights_status": "approved",
                     "content_sha256": "c"*64, "evidence_span": "Wrong company"},
                    {"organisation_number": org, "signal_type": "public_post",
                     "exact_entity": True, "source_url": "https://squarespace.com/news/unrelated",
                     "published_at": date.today().isoformat(), "rights_status": "approved",
                     "content_sha256": "d"*64, "evidence_span": "Squarespace is unrelated"},
                    {"organisation_number": org, "signal_type": "profile_metrics",
                     "exact_entity": True, "source_url": site,
                     "published_at": date.today().isoformat(), "rights_status": "approved",
                     "content_sha256": "e"*64, "evidence_span": "Not a dated news story"}
                ]
            }}
        }
    }
    result=answer_profile(base, "Give me a company overview")
    facts=[f for f in result["facts"] if f["classification"].startswith("verified_company_site_")]
    assert len(facts)==2
    assert {x["claim"] for x in facts}=={"Verified company-site news","Verified company-site job posting"}
    assert all(x["source_url"].startswith(site) for x in facts)
    base["evidence"]["website"]["value"]["identity_assessment"]["publishable"]=False
    result2=answer_profile(base,"Give me a company overview")
    assert not any(f["classification"].startswith("verified_company_site_") for f in result2["facts"])


def test_official_registry_facts_extend_synthesis_without_unverified_website_claims():
    from norway_company_agent.research import answer_profile
    source="https://data.brreg.no/enhetsregisteret/api/enheter/999999991"
    profile={
        "organisation_number":"999999991","name":"EXAMPLE COMPANY AS",
        "industry":{"kode":"62.010","beskrivelse":"Computer programming"},
        "bankrupt":False,"liquidating":False,
        "latest_submitted_accounts":"2025",
        "business_address":{"adresse":["Main Street 4"],"postnummer":"0150","poststed":"OSLO","land":"Norge"},
        "website":"https://unverified-supplier.com",
        "evidence":{"registry":{"status":"available","source_url":source,"retrieved_at":"2026-11-13T00:00:00Z"}}
    }
    summary=answer_profile(profile,"Give me a company overview")
    labels={f["claim"] for f in summary["facts"]}
    assert {"Registered industry","Registered industry code","Bankruptcy flag",
            "Registered business address","Latest reported annual accounts period"} <= labels
    assert "Registry-listed verified website" not in labels
    assert all(f["source_url"]==source for f in summary["facts"] if f["classification"]=="official_registry_fact")
    assert any(f["claim"]=="Bankruptcy flag" and f["value"] is False for f in summary["facts"])
    assert not any(f["classification"]=="company_reported_claim" for f in summary["facts"])
