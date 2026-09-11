from __future__ import annotations

import argparse
import collections
import datetime as dt
from pathlib import Path

from .analysis import STATES
from .util import iso_z, load_json, parse_time, stable_id, utcnow, write_json


STATE_QUOTAS = {
    "CONFIRMED": 28,
    "CREDIBLE REPORT": 42,
    "EARLY WARNING": 46,
    "SPECULATIVE": 24,
    "UNVERIFIED CLAIM": 20,
    "REFUTED": 12,
    "DORMANT": 8,
}
KIND_ORDER = {"ACTOR": 0, "DOMAIN": 1, "REGION": 2, "CLAIM": 3, "SOURCE": 4, "ANOMALY": 5, "HISTORICAL": 6}
LAYER_ORDER = {"DIRECT": 0, "REPORTED": 1, "ANALYTICAL": 2, "HISTORICAL": 3}


def _mask(kind: str, *parts: object) -> str:
    prefix = {
        "CLAIM": "EVENT",
        "ACTOR": "ACTOR",
        "DOMAIN": "DOMAIN",
        "REGION": "AREA",
        "SOURCE": "SOURCE",
        "ANOMALY": "PATTERN",
        "HISTORICAL": "HISTORY",
    }.get(kind, "NODE")
    return f"{prefix}-{stable_id(kind, *parts, length=4).upper()}"


def _claim_sort_key(claim: dict) -> tuple:
    return (
        int(claim.get("watch_priority") or 0),
        int(claim.get("confidence") or 0),
        str(claim.get("material_time") or ""),
        str(claim.get("id") or ""),
    )


def _select_claims(claims: list[dict], now: dt.datetime, limit: int) -> list[dict]:
    eligible = []
    for claim in claims:
        if not claim.get("id") or claim.get("state") not in STATES:
            continue
        age = now - parse_time(claim.get("material_time"), now)
        if age < -dt.timedelta(hours=6):
            continue
        state = claim.get("state")
        horizon = 365 if state == "DORMANT" else 120 if state == "REFUTED" else 30
        if age <= dt.timedelta(days=horizon):
            eligible.append(claim)

    by_state: dict[str, list[dict]] = collections.defaultdict(list)
    for claim in eligible:
        by_state[claim["state"]].append(claim)
    for rows in by_state.values():
        rows.sort(key=_claim_sort_key, reverse=True)

    selected: list[dict] = []
    seen: set[str] = set()
    for state in STATES:
        for claim in by_state.get(state, [])[: STATE_QUOTAS[state]]:
            if len(selected) >= limit:
                break
            selected.append(claim)
            seen.add(claim["id"])

    if len(selected) < limit:
        for claim in sorted(eligible, key=_claim_sort_key, reverse=True):
            if claim["id"] in seen:
                continue
            selected.append(claim)
            seen.add(claim["id"])
            if len(selected) >= limit:
                break
    return sorted(selected, key=_claim_sort_key, reverse=True)


def _compact_claim(claim: dict) -> dict:
    return {
        "id": claim.get("id"),
        "headline": claim.get("headline"),
        "state": claim.get("state"),
        "confidence": claim.get("confidence", 0),
        "watch_priority": claim.get("watch_priority", 0),
        "threat_score": claim.get("threat_score", 0),
        "material_time": claim.get("material_time"),
        "domains": claim.get("domains", []),
        "regions": claim.get("regions", []),
        "actors": claim.get("actors", []),
        "sources": claim.get("sources", []),
        "independent_provenance_count": claim.get("independent_provenance_count", 0),
        "classification_reason": claim.get("classification_reason"),
        "evidence": claim.get("evidence", [])[:3],
    }


def build_edges_product(
    claims: list[dict],
    anomalies: list[dict],
    now: dt.datetime | None = None,
    claim_limit: int = 180,
) -> dict:
    """Build the bounded public relationship graph used by the EDGES interface.

    Direct attribution, reported association, analytical overlap, and historical
    resemblance stay separate. No edge is allowed to silently become a claim of
    coordination, control, intent, or culpability.
    """

    now = now or utcnow()
    selected = _select_claims(claims, now, claim_limit)
    selected_by_id = {claim["id"]: claim for claim in selected}
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    incident_claims: dict[str, set[str]] = collections.defaultdict(set)

    def add_node(node_id: str, kind: str, label: str, **extra) -> str:
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "label": label,
                "masked_label": _mask(kind, node_id),
                **extra,
            }
        return node_id

    def add_edge(
        source: str,
        target: str,
        relationship: str,
        layer: str,
        explanation: str,
        *,
        confidence: int = 0,
        evidence_state: str | None = None,
        weight: int = 1,
        evidence: list[dict] | None = None,
    ) -> None:
        edge_id = f"edge-{stable_id(source, target, relationship, layer, length=18)}"
        if edge_id in edges:
            return
        edges[edge_id] = {
            "id": edge_id,
            "source": source,
            "target": target,
            "relationship": relationship,
            "layer": layer,
            "confidence": max(0, min(100, int(confidence or 0))),
            "evidence_state": evidence_state,
            "weight": max(1, min(5, int(weight or 1))),
            "explanation": explanation,
            "evidence": evidence or [],
        }
        if source in selected_by_id:
            incident_claims[target].add(source)
        if target in selected_by_id:
            incident_claims[source].add(target)

    for claim in selected:
        claim_id = claim["id"]
        evidence = [
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "source_class": row.get("source_class"),
                "provenance_root": row.get("provenance_root"),
                "stance": row.get("stance"),
                "published": row.get("published"),
                "url": row.get("url"),
                "discovery_only": bool(row.get("discovery_only")),
            }
            for row in claim.get("evidence", [])[:5]
        ]
        add_node(
            claim_id,
            "CLAIM",
            claim.get("headline") or "Untitled claim",
            state=claim.get("state"),
            confidence=int(claim.get("confidence") or 0),
            confidence_direction=claim.get("confidence_direction"),
            watch_priority=int(claim.get("watch_priority") or 0),
            threat_score=int(claim.get("threat_score") or 0),
            material_time=claim.get("material_time"),
            domains=claim.get("domains", []),
            regions=claim.get("regions", []),
            actors=claim.get("actors", []),
            independent_provenance_count=int(claim.get("independent_provenance_count") or 0),
            classification_reason=claim.get("classification_reason"),
            discovery_only=bool(claim.get("discovery_only")),
            evidence=evidence,
        )
        incident_claims[claim_id].add(claim_id)

        for actor in sorted(set(claim.get("actors", []))):
            actor_id = f"actor-{stable_id(actor, length=14)}"
            add_node(actor_id, "ACTOR", actor, description="Named actor extracted from public reporting.")
            add_edge(
                claim_id,
                actor_id,
                "MENTIONS_ACTOR",
                "REPORTED",
                "The actor appears in the claim's reporting. Mention does not establish responsibility, coordination, or intent.",
                confidence=claim.get("confidence", 0),
                evidence_state=claim.get("state"),
                weight=2,
            )

        for domain in sorted(set(claim.get("domains", []))):
            domain_id = f"domain-{stable_id(domain, length=14)}"
            add_node(domain_id, "DOMAIN", domain, description="Y&Y analytical domain classification.")
            add_edge(
                claim_id,
                domain_id,
                "CLASSIFIED_AS",
                "REPORTED",
                "Y&Y classified the claim in this domain from the reported content.",
                confidence=claim.get("confidence", 0),
                evidence_state=claim.get("state"),
                weight=2,
            )

        for region in sorted(set(claim.get("regions", [])) - {"GLOBAL"}):
            region_id = f"region-{stable_id(region, length=14)}"
            add_node(region_id, "REGION", region, description="Geographic area extracted from public reporting.")
            add_edge(
                claim_id,
                region_id,
                "REPORTED_LOCATION",
                "REPORTED",
                "The claim was tagged to this geography. Geographic overlap alone is not evidence of coordination.",
                confidence=claim.get("confidence", 0),
                evidence_state=claim.get("state"),
                weight=2,
            )

        seen_roots: set[str] = set()
        for row in evidence:
            root = str(row.get("provenance_root") or "").strip()
            if not root or root in seen_roots:
                continue
            seen_roots.add(root)
            source_id = f"source-{stable_id(root, length=14)}"
            add_node(
                source_id,
                "SOURCE",
                row.get("source") or root,
                source_class=row.get("source_class"),
                provenance_root=root,
                description="Originating provenance root; republication does not create an independent source.",
            )
            stance = "CONTRADICTS" if row.get("stance") == "refutation" else "ATTRIBUTES"
            add_edge(
                claim_id,
                source_id,
                stance,
                "DIRECT",
                "A retained observation directly attributes this claim to the displayed provenance root.",
                confidence=claim.get("confidence", 0),
                evidence_state=claim.get("state"),
                weight=3 if stance == "ATTRIBUTES" else 4,
                evidence=[row],
            )
            if len(seen_roots) >= 3:
                break

    # Cross-domain links are useful discovery cues, but remain analytical even
    # when both underlying claims have high confidence.
    seen_cross_pairs: set[tuple[str, str]] = set()
    for claim in selected:
        for link in claim.get("cross_domain_links", []):
            other_id = link.get("claim_id")
            if other_id not in selected_by_id:
                continue
            pair = tuple(sorted((claim["id"], other_id)))
            if pair in seen_cross_pairs:
                continue
            seen_cross_pairs.add(pair)
            other = selected_by_id[other_id]
            shared = sorted(set(link.get("shared_actors", [])) | set(link.get("shared_regions", [])))
            detail = ", ".join(shared) if shared else "a shared analytical key"
            add_edge(
                claim["id"],
                other_id,
                "CROSS_DOMAIN_OVERLAP",
                "ANALYTICAL",
                f"The claims cross domains and share {detail}. This is a discovery cue, not proof of coordination.",
                confidence=min(int(claim.get("confidence") or 0), int(other.get("confidence") or 0)),
                weight=min(5, 1 + len(shared)),
            )

    active_anomalies = []
    for anomaly in anomalies:
        members = [claim_id for claim_id in anomaly.get("claim_ids", []) if claim_id in selected_by_id]
        if len(members) < 2:
            continue
        active_anomalies.append((anomaly, members))
    active_anomalies.sort(key=lambda item: int(item[0].get("priority") or 0), reverse=True)
    for anomaly, members in active_anomalies[:20]:
        anomaly_id = anomaly["id"]
        add_node(
            anomaly_id,
            "ANOMALY",
            f"CONVERGENCE: {anomaly.get('subject') or 'UNRESOLVED'}",
            priority=int(anomaly.get("priority") or 0),
            domains=anomaly.get("domains", []),
            description=anomaly.get("reason"),
        )
        for claim_id in members:
            add_edge(
                claim_id,
                anomaly_id,
                "CONVERGENCE_MEMBER",
                "ANALYTICAL",
                "The claim contributes to a near-time cross-domain convergence cue. This is not proof of a common cause.",
                confidence=int(selected_by_id[claim_id].get("confidence") or 0),
                weight=2,
            )

    historical_nodes = 0
    for claim in selected:
        for match in claim.get("historical_matches", [])[:1]:
            match_id = match.get("claim_id")
            if not match_id:
                continue
            if match_id in selected_by_id:
                target_id = match_id
            elif historical_nodes < 36:
                target_id = f"history-{stable_id(match_id, length=16)}"
                if target_id not in nodes:
                    historical_nodes += 1
                add_node(
                    target_id,
                    "HISTORICAL",
                    match.get("headline") or "Retained historical claim",
                    material_time=match.get("material_time"),
                    description="Retained historical memory used for recurrence comparison.",
                )
            else:
                continue
            add_edge(
                claim["id"],
                target_id,
                "HISTORICAL_RESEMBLANCE",
                "HISTORICAL",
                "The records share actor/region and domain features across time. Resemblance does not establish repetition or common authorship.",
                confidence=int(claim.get("confidence") or 0),
                weight=1,
            )

    degree = collections.Counter()
    layer_degree: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    neighbor_kinds: dict[str, set[str]] = collections.defaultdict(set)
    for edge in edges.values():
        source, target = edge["source"], edge["target"]
        degree[source] += 1
        degree[target] += 1
        layer_degree[source][edge["layer"]] += 1
        layer_degree[target][edge["layer"]] += 1
        neighbor_kinds[source].add(nodes[target]["kind"])
        neighbor_kinds[target].add(nodes[source]["kind"])

    for node_id, node in nodes.items():
        node["degree"] = degree[node_id]
        node["claim_count"] = len(incident_claims[node_id])
        node["layer_counts"] = dict(layer_degree[node_id])

    bridges = []
    for node in nodes.values():
        if node["kind"] in {"CLAIM", "HISTORICAL"}:
            continue
        bridge_score = node["degree"] * (1 + 0.25 * len(neighbor_kinds[node["id"]]))
        bridges.append({
            "id": node["id"],
            "kind": node["kind"],
            "label": node["label"],
            "masked_label": node["masked_label"],
            "degree": node["degree"],
            "claim_count": node["claim_count"],
            "bridge_score": round(bridge_score, 2),
        })
    bridges.sort(key=lambda row: (row["bridge_score"], row["degree"], row["id"]), reverse=True)

    node_rows = sorted(nodes.values(), key=lambda row: (KIND_ORDER.get(row["kind"], 99), -row["degree"], row["id"]))
    edge_rows = sorted(edges.values(), key=lambda row: (LAYER_ORDER.get(row["layer"], 99), row["relationship"], row["id"]))
    state_counts = collections.Counter(claim.get("state") for claim in selected)
    layer_counts = collections.Counter(edge["layer"] for edge in edge_rows)

    return {
        "generated_at": iso_z(now),
        "title": "Y&Y // EDGES",
        "window": "Topologically useful claims from the last 30 days, plus bounded refuted and dormant context.",
        "safeguard": "An edge means direct attribution, reported association, machine-detected overlap, or historical resemblance exactly as labeled. It does not prove coordination, control, intent, partnership, or guilt.",
        "mode_note": "NAMES shows public labels. MASKS preserves stable identity while suppressing labels. EDGES removes visible names so topology can be inspected before identity shapes interpretation.",
        "states": list(STATES),
        "layers": ["DIRECT", "REPORTED", "ANALYTICAL", "HISTORICAL"],
        "stats": {
            "claims": len(selected),
            "nodes": len(node_rows),
            "edges": len(edge_rows),
            "state_counts": dict(state_counts),
            "layer_counts": dict(layer_counts),
            "anomalies": len(active_anomalies[:20]),
        },
        "nodes": node_rows,
        "edges": edge_rows,
        "bridges": bridges[:16],
        "top_claims": [_compact_claim(claim) for claim in selected[:12]],
        "methodology": {
            "direct": "A retained observation points to an originating provenance root.",
            "reported": "An actor, place, or domain was extracted or classified from a public report.",
            "analytical": "Claims share a bounded actor, geography, domain, or anomaly key. This is a cue for review, not a factual claim of linkage.",
            "historical": "A current claim resembles retained history across actor/region and domain features.",
            "provenance": "Syndicated rewrites retain one originating root and do not manufacture corroboration.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Y&Y EDGES relationship product from retained claims")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    data = args.root / "data"
    claims_doc = load_json(data / "claims.json", {})
    anomaly_doc = load_json(data / "anomalies.json", {})
    status = load_json(data / "autonomy-status.json", {})
    now = parse_time(status.get("last_poll"), utcnow())
    product = build_edges_product(claims_doc.get("claims", []), anomaly_doc.get("anomalies", []), now)
    write_json(data / "edges-live.json", product)
    print(f"Y&Y EDGES built: {product['stats']['nodes']} nodes / {product['stats']['edges']} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
