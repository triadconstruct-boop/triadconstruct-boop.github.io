from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

from scripts.yy_engine.analysis import (
    STATES,
    add_cross_domain_links,
    add_historical_matches,
    build_claims,
    build_threshold,
    build_wwt,
    detect_anomalies,
    enrich_item,
)
from scripts.yy_engine.ingest import _health
from scripts.yy_engine.relationships import build_edges_product

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def raw(
    title: str,
    source_id: str = "wire-a",
    source_class: str = "wire",
    reliability: float = 0.94,
    evidence_type: str = "reported_fact",
    hours_ago: int = 1,
    summary: str = "",
    ownership_root: str | None = None,
) -> dict:
    return {
        "title": title,
        "summary": summary,
        "url": f"https://{source_id}.example/{abs(hash((title, source_id)))}",
        "published": (NOW - dt.timedelta(hours=hours_ago)).isoformat(),
        "source_id": source_id,
        "source": source_id,
        "source_class": source_class,
        "source_reliability": reliability,
        "evidence_type": evidence_type,
        "ownership_root": ownership_root or source_id,
        "default_domain": "SECURITY",
    }


def claims_for(*items: dict, now: dt.datetime = NOW, prior: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    observations = [enrich_item(item, now) for item in items]
    return build_claims(observations, prior or [], now), observations


class EngineRegressionTests(unittest.TestCase):
    def test_all_required_states_are_declared(self):
        self.assertEqual(set(STATES), {"CONFIRMED", "CREDIBLE REPORT", "EARLY WARNING", "SPECULATIVE", "UNVERIFIED CLAIM", "REFUTED", "DORMANT"})

    def test_single_credible_wire_is_not_confirmed(self):
        claims, _ = claims_for(raw("Reuters reports Russian military strike near Ukraine border"))
        self.assertEqual(claims[0]["state"], "CREDIBLE REPORT")

    def test_republication_does_not_create_independent_corroboration(self):
        one = raw("Russian military strike reported near Ukraine border", "outlet-a", "established_media", .84, summary="According to Reuters, the strike occurred.")
        two = raw("Russian military strike reported near Ukraine border", "outlet-b", "established_media", .84, summary="Reuters reported the same strike.")
        claims, _ = claims_for(one, two)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["independent_provenance_count"], 1)
        self.assertNotEqual(claims[0]["state"], "CONFIRMED")

    def test_independent_corroboration_raises_confidence(self):
        one = raw("Russian military strike reported near Ukraine border", "wire-a")
        two = raw("Russian military strike reported near Ukraine border", "wire-b")
        single, _ = claims_for(one)
        combined, _ = claims_for(one, two)
        self.assertGreater(combined[0]["confidence"], single[0]["confidence"])
        self.assertEqual(combined[0]["state"], "CONFIRMED")

    def test_weak_warning_moves_watch_more_than_threat(self):
        claims, _ = claims_for(raw(
            "Warning: Russian troops prepare near Ukraine and may signal escalation",
            "regional", "regional_local", .68, "regional_report",
        ))
        self.assertEqual(claims[0]["state"], "EARLY WARNING")
        self.assertGreater(claims[0]["watch_priority"], claims[0]["threat_score"])

    def test_refutation_is_preserved_and_zeroed(self):
        claims, _ = claims_for(raw(
            "Officials refuted fabricated cyberattack claim against United States power grid",
            "official", "primary_official", .97, "official_statement",
            summary="Technical investigators found no evidence the alleged strike occurred.",
        ))
        self.assertEqual(claims[0]["state"], "REFUTED")
        self.assertEqual((claims[0]["threat_score"], claims[0]["watch_priority"]), (0, 0))
        self.assertTrue(claims[0]["contradictory_observation_ids"])

    def test_material_time_decay_lowers_confidence(self):
        item = raw("Reuters reports Russian military strike near Ukraine border")
        first, observations = claims_for(item)
        later = NOW + dt.timedelta(days=10)
        decayed = build_claims(observations, first, later)
        self.assertLess(decayed[0]["confidence"], first[0]["confidence"])
        self.assertEqual(decayed[0]["confidence_direction"], "DOWN")

    def test_historical_replay_cases(self):
        fixtures = json.loads((Path(__file__).parent / "fixtures" / "historical_cases.json").read_text())
        for index, fixture in enumerate(fixtures):
            with self.subTest(fixture["name"]):
                item = raw(
                    fixture["title"], f"fixture-{index}", fixture["source_class"],
                    fixture["reliability"], fixture["evidence_type"], summary=fixture["summary"],
                )
                claims, _ = claims_for(item)
                self.assertEqual(claims[0]["state"], fixture["expected_state"])

    def test_threshold_separates_confirmed_and_precursor(self):
        confirmed = raw(
            "CISA confirms ransomware disruption at United States Colonial Pipeline critical infrastructure",
            "cisa", "primary_official", .99, "official_data",
        )
        speculative = raw(
            "Rumor claims terrorists may attack an American airport",
            "signal", "low_confidence", .40, "user_submitted_claim",
        )
        claims, observations = claims_for(confirmed, speculative)
        result = build_threshold(claims, observations, NOW)
        self.assertEqual(result["confirmed_homeland_signal"]["claim_count"], 1)
        self.assertEqual(result["precursor_speculative_signal"]["claim_count"], 1)

    def test_wwt_separates_verified_and_early_warning_pressure(self):
        verified = raw(
            "IAEA records nuclear enrichment activity by Iran",
            "iaea", "primary_official", .98, "official_data",
        )
        warning = raw(
            "Warning: Russian troops mobilization near Ukraine may signal escalation",
            "regional", "regional_local", .68, "regional_report",
        )
        claims, observations = claims_for(verified, warning)
        result = build_wwt(claims, observations, NOW)
        self.assertEqual(result["verified_pressure"]["claim_count"], 1)
        self.assertEqual(result["early_warning_pressure"]["claim_count"], 1)

    def test_cross_domain_convergence_creates_anomaly(self):
        cyber = raw("Russian malware intrusion targets banks in Ukraine", "cyber-source", "specialist", .82, "specialist_report")
        war = raw("Russian troops mobilize near Ukraine border", "war-source", "regional_local", .72, "regional_report")
        claims, _ = claims_for(cyber, war)
        add_cross_domain_links(claims, NOW)
        anomalies = detect_anomalies(claims, NOW)
        self.assertTrue(anomalies)
        self.assertTrue(any(claim["cross_domain_links"] for claim in claims))

    def test_edges_preserve_evidence_boundaries(self):
        cyber = raw("Russian malware intrusion targets banks in Ukraine", "cyber-source", "specialist", .82, "specialist_report")
        war = raw("Russian troops mobilize near Ukraine border", "war-source", "regional_local", .72, "regional_report")
        claims, _ = claims_for(cyber, war)
        add_cross_domain_links(claims, NOW)
        anomalies = detect_anomalies(claims, NOW)
        product = build_edges_product(claims, anomalies, NOW, claim_limit=20)
        layers = {edge["layer"] for edge in product["edges"]}
        relationships = {edge["relationship"] for edge in product["edges"]}
        self.assertTrue({"DIRECT", "REPORTED", "ANALYTICAL"}.issubset(layers))
        self.assertIn("MENTIONS_ACTOR", relationships)
        self.assertIn("CROSS_DOMAIN_OVERLAP", relationships)
        self.assertIn("not prove", product["safeguard"].lower())
        self.assertTrue(all(node.get("masked_label") for node in product["nodes"]))
        node_ids = {node["id"] for node in product["nodes"]}
        self.assertTrue(all(edge["source"] in node_ids and edge["target"] in node_ids for edge in product["edges"]))

    def test_historical_recurrence_is_attached(self):
        current = raw("Russian troops mobilize near Ukraine border", "current", "regional_local", .72, "regional_report")
        claims, _ = claims_for(current)
        memory = [{
            "id": "historic", "headline": "Earlier Russian troop buildup near Ukraine",
            "material_time": (NOW - dt.timedelta(days=90)).isoformat(),
            "domains": ["WAR"], "regions": ["RUSSIA", "UKRAINE"], "actors": ["RUSSIA", "UKRAINE"],
        }]
        before = claims[0]["watch_priority"]
        add_historical_matches(claims, memory, NOW)
        self.assertTrue(claims[0]["historical_matches"])
        self.assertGreater(claims[0]["watch_priority"], before)

    def test_sparse_sensor_can_be_quiet_without_failure(self):
        source = {"id": "sensor", "name": "Sensor", "url": "https://example.test", "source_class": "primary_official", "reliability": .99, "sparse_ok": True}
        health = _health(source, [], None, {}, NOW)
        self.assertEqual(health["status"], "quiet")
        self.assertTrue(health["reachable"])


if __name__ == "__main__":
    unittest.main()
