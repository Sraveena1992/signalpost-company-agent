import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"src"))
from bs4 import BeautifulSoup
from norway_company_agent.website import _company_linked_ats
from scripts.diagnose_exact_500_jobs import diagnostic

def test_ats_link_has_exact_verified_company_page_provenance():
    html='''<a href="https://acme.teamtailor.com/jobs/123?ref=home">Ledige stillinger</a>
    <a href="https://boards.greenhouse.io/acme">Jobs</a>
    <a href="https://teamtailor.com.evil.example/job">Spoofed ATS</a>
    <a href="https://unrelated.example/jobs">unrelated</a>'''
    result=_company_linked_ats("https://acme.no/karriere",BeautifulSoup(html,"html.parser"))
    assert len(result)==2
    assert all(x["linked_from"]=="https://acme.no/karriere" for x in result)
    assert any(x["ats_host"]=="teamtailor.com" for x in result)
    assert all("evil" not in x["url"] for x in result)

def test_ats_candidate_not_a_verified_job():
    p={"organisation_number":"123456789","name":"ACME AS","evidence":{
      "website":{"status":"available","retrieved_at":"2026-11-14T10:00:00Z",
        "value":{"identity_assessment":{"publishable":True},"pages":[],
          "ats_links_found":[{"url":"https://acme.teamtailor.com/jobs",
                              "linked_from":"https://acme.no/karriere","ats_host":"teamtailor.com"}]}},
      "public_activity":{"status":"not_found"}}}
    row=diagnostic(p)
    assert row["ats_candidate_urls"]==["https://acme.teamtailor.com/jobs"]
    assert row["verified_site_jobs"]==0
    assert row["status"]=="ats_links_not_explored"
