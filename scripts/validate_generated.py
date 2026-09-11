#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REQUIRED_STATES = {"CONFIRMED", "CREDIBLE REPORT", "EARLY WARNING", "SPECULATIVE", "UNVERIFIED CLAIM", "REFUTED", "DORMANT"}
REQUIRED_COMPONENTS = {
    "source_quality", "independence", "corroboration", "contradiction", "specificity",
    "recency", "evidence_type", "historical_reliability", "claim_maturity",
}
REQUIRED_CLASSES = {
    "primary_official", "wire", "established_media", "specialist", "regional_local",
    "osint", "expert", "low_confidence", "discovery",
}


def load(name: str):
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"missing generated file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_score(value, label: str) -> None:
    if not isinstance(value, int) or not 0 <= value <= 100:
        raise SystemExit(f"invalid {label}: {value!r}")


def main() -> int:
    catalog = json.loads((ROOT / "config" / "source-catalog.json").read_text(encoding="utf-8"))
    enabled = [source for source in catalog["sources"] if source.get("enabled", True)]
    classes = {source["source_class"] for source in enabled}
    if len(enabled) < 50:
        raise SystemExit(f"source catalog is too narrow: {len(enabled)} enabled")
    if missing := REQUIRED_CLASSES - classes:
        raise SystemExit(f"source classes missing: {sorted(missing)}")
    if len({source["id"] for source in catalog["sources"]}) != len(catalog["sources"]):
        raise SystemExit("duplicate source IDs")

    status = load("autonomy-status.json")
    observations = load("observations.json").get("observations", [])
    claims_doc = load("claims.json")
    claims = claims_doc.get("claims", [])
    audits = load("audit-log.json").get("records", [])
    memory = load("historical-memory.json").get("claims", [])
    load("anomalies.json")
    edges_product = load("edges-live.json")
    worldwatch = load("worldwatch-live.json")
    threshold = load("threshold-live.json")
    wwt = load("wwt-live.json")
    for name in ("live-events.json", "atlas-live.json", "infrawatch-live.json", "trfk-live.json", "brief-live.json", "source-registry.json"):
        load(name)

    if str(status.get("version")) != "3.0" or not status.get("last_poll"):
        raise SystemExit("status is not a timestamped v3 result")
    if not 0 <= int(status.get("source_health_percent", -1)) <= 100:
        raise SystemExit("invalid source coverage")
    if status.get("situation") not in {"ACTIVE WITH COVERAGE", "ACTIVE WITH GAPS", "QUIET WITH COVERAGE", "QUIET WITH DISCOVERY GAP", "COLLECTION GAP"}:
        raise SystemExit("missing explicit quiet/coverage interpretation")
    if set(claims_doc.get("states", [])) != REQUIRED_STATES:
        raise SystemExit("generated state vocabulary is incomplete")

    observation_ids = [row.get("id") for row in observations]
    if None in observation_ids or len(observation_ids) != len(set(observation_ids)):
        raise SystemExit("observation IDs are missing or duplicated")
    assignments = Counter(oid for claim in claims for oid in claim.get("observation_ids", []))
    if set(assignments) != set(observation_ids) or any(count != 1 for count in assignments.values()):
        raise SystemExit("every observation must belong to exactly one claim")

    audit_ids = {row.get("claim_id") for row in audits}
    for claim in claims:
        cid = claim.get("id")
        if not cid or claim.get("state") not in REQUIRED_STATES:
            raise SystemExit(f"invalid claim state/id: {cid}")
        require_score(claim.get("confidence"), f"confidence for {cid}")
        require_score(claim.get("threat_score"), f"threat score for {cid}")
        require_score(claim.get("watch_priority"), f"watch priority for {cid}")
        if set(claim.get("confidence_components", {})) != REQUIRED_COMPONENTS:
            raise SystemExit(f"confidence components incomplete for {cid}")
        if not claim.get("classification_reason") or not claim.get("branch_analysis"):
            raise SystemExit(f"reason/branch analysis missing for {cid}")
        if "historical_matches" not in claim:
            raise SystemExit(f"historical match field missing for {cid}")
        if claim.get("discovery_only") and claim.get("state") in {"CONFIRMED", "CREDIBLE REPORT"}:
            raise SystemExit(f"discovery-only claim entered hard evidence layer: {cid}")
        if claim.get("state") == "REFUTED" and (claim.get("threat_score") or claim.get("watch_priority")):
            raise SystemExit(f"refuted claim affects scores: {cid}")
        if cid not in audit_ids:
            raise SystemExit(f"audit missing for {cid}")

    if len(memory) < len(claims):
        raise SystemExit("historical memory failed to preserve current claims")
    if not isinstance(worldwatch.get("claims"), list):
        raise SystemExit("WORLDWATCH layered claim stream missing")
    graph_nodes = edges_product.get("nodes", [])
    graph_edges = edges_product.get("edges", [])
    node_ids = [node.get("id") for node in graph_nodes]
    node_id_set = set(node_ids)
    edge_ids = [edge.get("id") for edge in graph_edges]
    if not graph_nodes or not graph_edges:
        raise SystemExit("EDGES relationship product is empty")
    if None in node_ids or len(node_ids) != len(set(node_ids)):
        raise SystemExit("EDGES node IDs are missing or duplicated")
    if None in edge_ids or len(edge_ids) != len(set(edge_ids)):
        raise SystemExit("EDGES edge IDs are missing or duplicated")
    if any(not node.get("masked_label") for node in graph_nodes):
        raise SystemExit("EDGES stable masked labels are incomplete")
    if any(edge.get("source") not in node_id_set or edge.get("target") not in node_id_set for edge in graph_edges):
        raise SystemExit("EDGES contains a dangling relationship")
    if any(edge.get("layer") not in {"DIRECT", "REPORTED", "ANALYTICAL", "HISTORICAL"} for edge in graph_edges):
        raise SystemExit("EDGES contains an unlabeled evidence layer")
    if "not prove" not in str(edges_product.get("safeguard", "")).lower():
        raise SystemExit("EDGES coordination/culpability safeguard is missing")
    for document, hard_key, early_key in (
        (threshold, "confirmed_homeland_signal", "precursor_speculative_signal"),
        (wwt, "verified_pressure", "early_warning_pressure"),
    ):
        for key in (hard_key, early_key):
            if key not in document:
                raise SystemExit(f"dual signal missing: {key}")
            require_score(document[key].get("score"), key)
        for claim in document[hard_key].get("top_claims", []):
            if hard_key == "confirmed_homeland_signal" and claim.get("state") != "CONFIRMED":
                raise SystemExit("non-confirmed claim leaked into Confirmed Homeland Signal")
            if hard_key == "verified_pressure" and claim.get("state") not in {"CONFIRMED", "CREDIBLE REPORT"}:
                raise SystemExit("weak claim leaked into Verified Pressure")

    print(f"Y&Y generated-data validation passed: {len(enabled)} enabled sources, {len(observations)} observations, {len(claims)} claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
