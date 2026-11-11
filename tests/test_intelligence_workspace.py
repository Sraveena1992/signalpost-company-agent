from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_exists_with_accessible_forms():
    page = (ROOT / "static" / "intelligence.html").read_text(encoding="utf-8")
    assert 'id="searchForm"' in page
    assert 'id="ainput"' in page
    assert 'id="binput"' in page
    assert 'id="financialStatus"' in page
    assert 'id="aevidence"' in page
    assert 'id="bevidence"' in page


def test_workspace_uses_real_endpoints_and_no_demo_values():
    page = (ROOT / "static" / "intelligence.html").read_text(encoding="utf-8")
    assert "/api/search?q=" in page
    assert "/api/company/" in page
    assert "/api/research/" in page
    assert "No figures are invented" in page
    assert "Research not requested" in page


def test_render_page_links_workspace():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'href="/static/intelligence.html"' in source
