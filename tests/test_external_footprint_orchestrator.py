from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_external_footprint import site_observations  # noqa: E402
from norway_company_agent.external_footprint import publishable_observation  # noqa: E402


class ExternalFootprintOrchestratorTests(unittest.TestCase):
    def profile(self, publishable: bool) -> dict:
        return {
            "organisation_number": "999999999",
            "evidence": {
                "website": {
                    "status": "available",
                    "retrieved_at": "2026-09-29T00:00:00Z",
                    "value": {
                        "final_url": "https://example.no/",
                        "content_sha256": "a" * 64,
                        "identity_assessment": {
                            "publishable": publishable,
                            "promotion_proof": [{"type": "org_number"}],
                        },
                        "social_links": [{"platform": "youtube", "url": "https://youtube.com/example"}],
                        "pages": [{
                            "url": "https://example.no/news/latest",
                            "title": "Latest company update",
                            "content_sha256": "b" * 64,
                        }],
                    },
                }
            },
        }

    def test_unverified_site_produces_no_external_publication(self):
        self.assertEqual(site_observations(self.profile(False)), [])

    def test_verified_site_produces_evidence_complete_observations(self):
        rows = site_observations(self.profile(True))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["signal_type"] for row in rows}, {"profile_handle", "public_post"})
        self.assertTrue(all(publishable_observation(row) for row in rows))


if __name__ == "__main__":
    unittest.main()
