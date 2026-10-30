from __future__ import annotations

import copy
import unittest

from scripts.yy_engine.worldwatch import build_worldwatch, geography


def claim(cid, headline, priority=50, regions=None, domains=None):
    return {
        "id": cid, "headline": headline, "watch_priority": priority,
        "confidence": 67, "threat_score": 30, "state": "CREDIBLE REPORT",
        "regions": regions or [], "domains": domains or ["WAR"],
        "evidence": [{"url": f"https://example.test/{cid}"}],
    }


class WorldwatchGeographyTests(unittest.TestCase):
    def test_regional_coverage_survives_the_feed_limit(self):
        # A region below the old top-250 cutoff must still reach the interface.
        rows = [claim(f"war-{i}", f"Russia Ukraine missile update {i}", 100 - i / 1000) for i in range(300)]
        rows += [claim("sudan", "Sudan aid corridor opens", 29), claim("taiwan", "Taiwan maritime warning", 28), claim("mexico", "Mexico security operation", 27)]
        product = build_worldwatch(rows, "2026-10-30T00:19:51Z", {}, limit=24)
        ids = {row["id"] for row in product["claims"]}
        self.assertTrue({"sudan", "taiwan", "mexico"} <= ids)
        self.assertEqual(len(ids), 24)
        self.assertEqual([row["id"] for row in product["claims"]], [row["id"] for row in rows if row["id"] in ids])

    def test_browsing_does_not_change_evidence_scores_or_inputs(self):
        rows = [claim("a", "Russia strikes Ukraine"), claim("b", "Gaza aid deliveries resume")]
        original = copy.deepcopy(rows)
        product = build_worldwatch(rows, "2026-10-30T00:19:51Z", {"CREDIBLE REPORT": 2})
        self.assertEqual(rows, original)
        for before, after in zip(original, product["claims"]):
            self.assertEqual(before, {key: value for key, value in after.items() if key != "worldwatch"})

    def test_headline_prevents_incidental_russia_tags_from_taking_a_desk(self):
        result = geography(claim("a", "Sudan aid corridor opens", regions=["RUSSIA", "UNITED STATES", "AFRICA"]))
        self.assertEqual(result["primary_region"], "sub-saharan-africa")
        self.assertEqual(result["regions"], ["sub-saharan-africa"])
        self.assertIn("sudan", result["conflicts"])

    def test_multi_region_claim_gets_only_one_allocation_desk(self):
        result = geography(claim("a", "China and Russia expand military cooperation"))
        self.assertEqual(result["primary_region"], "europe-eurasia")
        self.assertEqual(set(result["regions"]), {"europe-eurasia", "east-asia-pacific"})

    def test_missing_legacy_regions_are_recovered_from_headlines(self):
        for title, expected in (
            ("Pakistan Afghanistan border talks", "south-central-asia"),
            ("Australia warns of infrastructure damage", "east-asia-pacific"),
            ("Haiti emergency response", "latin-america-caribbean"),
            ("Yemen Red Sea shipping warning", "middle-east-north-africa"),
        ):
            with self.subTest(title=title):
                self.assertEqual(geography(claim("a", title))["primary_region"], expected)

    def test_unknown_and_multi_region_briefings_remain_global(self):
        self.assertEqual(geography(claim("a", "Global cyber vulnerability warning"))["primary_region"], "global")
        result = geography(claim("b", "Early Edition: October 29", regions=["RUSSIA", "IRAN", "UNITED STATES"]))
        self.assertEqual(result["primary_region"], "global")

    def test_small_conflict_within_a_busy_region_is_retained(self):
        rows = [claim(str(i), f"Russia Ukraine missile update {i}") for i in range(40)]
        rows.append(claim("baltic", "NATO Baltic maritime warning"))
        product = build_worldwatch(rows, "2026-10-30T00:19:51Z", {}, limit=3)
        self.assertIn("baltic", {row["id"] for row in product["claims"]})

    def test_empty_regions_and_counts_are_honest(self):
        product = build_worldwatch([claim("a", "Sudan aid corridor opens")], "2026-10-30T00:19:51Z", {})
        regions = {row["id"]: row for row in product["geography"]["regions"]}
        self.assertEqual(regions["sub-saharan-africa"]["count"], 1)
        self.assertEqual(regions["europe-eurasia"]["count"], 0)
        self.assertEqual(next(row for row in regions["sub-saharan-africa"]["conflicts"] if row["id"] == "sudan")["count"], 1)

    def test_foreign_statements_do_not_fill_multiple_overview_desks(self):
        for title, expected in (
            ("Melania Trump hopes humanitarian operation in Alyoshki will resolve Ukraine conflict", "europe-eurasia"),
            ("US imposes sanctions on Rwandan defence ministry over Congo rebels", "sub-saharan-africa"),
            ("North Korean workers sold into Russia", "east-asia-pacific"),
        ):
            self.assertEqual(geography(claim("a", title))["primary_region"], expected)

    def test_us_states_do_not_become_foreign_conflict_views(self):
        result = geography(claim("a", "New Mexico health system hit by cyberattack"))
        self.assertEqual(result["primary_region"], "north-america")
        self.assertNotIn("mexico-security", result["conflicts"])

