"""Syntax check the actual browser JavaScript embedded in the new workspace."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and not dict(attrs).get("src"):
            self.in_script = True

    def handle_data(self, data):
        if self.in_script:
            self.scripts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False


def test_intelligence_browser_javascript_syntax(tmp_path):
    if not shutil.which("node"):
        pytest.skip("Node.js unavailable on this host")
    markup = (Path(__file__).resolve().parents[1] / "static" / "intelligence.html").read_text(encoding="utf-8")
    parser = ScriptParser()
    parser.feed(markup)
    assert parser.scripts
    target = tmp_path / "intelligence.js"
    target.write_text("\n".join(parser.scripts), encoding="utf-8")
    result = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
