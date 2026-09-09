from __future__ import annotations

import argparse
import collections
import datetime as dt
from pathlib import Path

from . import ENGINE_VERSION, RULES_VERSION
from .analysis import (
    ACTIVE_STATES,
    STATES,
    add_cross_domain_links,
    add_historical_matches,
    audit_log,
    build_claims,
    build_threshold,
    build_wwt,
    confidence_distribution,
    detect_anomalies,
    merge_observations,
    update_historical_memory,
)
from .ingest import collect_sources, load_catalog
from .util import iso_z, load_json, parse_time, utcnow, write_json


def _source_summary(catalog: dict, health: list[dict]) -> dict:
    enabled = [source for source in catalog.get("sources", []) if source.get("enabled", True)]
    health_by_id = {row.get("id"): row for row in health}
    healthy = [row for row in health if row.get("status") in ("healthy", "quiet")]
    reachable = [row for row in health if row.get("reachable")]
    classes: dict[str, dict] = {}
    for source in enabled:
        name = source["source_class"]
        entry = classes.setdefault(name, {"configured": 0, "healthy": 0, "failed_or_stale": 0})
        entry["configured"] += 1
        status = health_by_id.get(source["id"], {}).get("status")
        if status in ("healthy", "quiet"):
            entry["healthy"] += 1
        elif status not in ("unpolled", None):
            entry["failed_or_stale"] += 1
    return {
        "configured": len(catalog.get("sources", [])),
        "enabled": len(enabled),
        "disabled": len(catalog.get("sources", [])) - len(enabled),
        "healthy_or_quiet": len(healthy),
        "reachable": len(reachable),
        "failed": sum(row.get("status") == "failed" for row in health),
        "empty": sum(row.get("status") == "empty" for row in health),
        "stale": sum(row.get("status") == "stale" for row in health),
        "quiet": sum(row.get("status") == "quiet" for row in health),
        "coverage_percent": round(len(healthy) / max(1, len(enabled)) * 100),
        "reachability_percent": round(len(reachable) / max(1, len(enabled)) * 100),
        "classes": classes,
    }


def _situation_label(active_count: int, coverage: int) -> str:
    if coverage < 60:
        return "COLLECTION GAP" if active_count else "QUIET WITH DISCOVERY GAP"
    if active_count:
        return "ACTIVE WITH COVERAGE" if coverage >= 90 else "ACTIVE WITH GAPS"
    return "QUIET WITH COVERAGE" if coverage >= 85 else "QUIET WITH DISCOVERY GAP"


def _offline_health(catalog: dict, prior_registry: dict, prior_status: dict) -> list[dict]:
    prior = prior_registry.get("sources", [])
    if prior and any("status" in row for row in prior):
        return prior
    old_rows = prior_status.get("source_status", [])
    old_by_id = {row.get("id"): row for row in old_rows}
    rows = []
    for source in catalog.get("sources", []):
        if not source.get("enabled", True):
            status = "disabled"
        elif source["id"] in old_by_id:
            status = "healthy" if old_by_id[source["id"]].get("ok") else "failed"
        else:
            status = "unpolled"
        old = old_by_id.get(source["id"], {})
        rows.append({
            "id": source["id"], "name": source["name"], "url": source["url"],
            "source_class": source["source_class"], "reliability": source.get("reliability"),
            "enabled": source.get("enabled", True), "status": status,
            "reachable": bool(old.get("ok")), "healthy": bool(old.get("ok")),
            "items": old.get("items", 0), "error": old.get("error"),
            "last_success": old.get("last_success"), "last_failure": old.get("last_failure"),
            "consecutive_failures": old.get("consecutive_failures", 0), "newest_item": None,
        })
    return rows


def _public_claim(claim: dict) -> dict:
    return claim


def run(root: Path, offline: bool = False, now: dt.datetime | None = None) -> dict:
    now = now or utcnow()
    data = root / "data"
    catalog = load_catalog(root / "config" / "source-catalog.json")
    prior_status = load_json(data / "autonomy-status.json", {})
    prior_registry = load_json(data / "source-registry.json", {})
    observations_document = load_json(data / "observations.json", {})
    if observations_document.get("observations") is None:
        observations_document = {"observations": load_json(data / "live-events.json", {}).get("events", [])}
    prior_observations = observations_document.get("observations", [])
    prior_claims = load_json(data / "claims.json", {}).get("claims", [])
    prior_memory = load_json(data / "historical-memory.json", {}).get("claims", [])

    if offline:
        items = []
        health = _offline_health(catalog, prior_registry, prior_status)
    else:
        items, health = collect_sources(catalog, prior_registry, now)

    observations, new_observations, future_rejected = merge_observations(items, prior_observations, now)
    claims = build_claims(observations, prior_claims, now)
    add_cross_domain_links(claims, now)
    add_historical_matches(claims, prior_memory, now)
    anomalies = detect_anomalies(claims, now)
    memory = update_historical_memory(claims, prior_memory, now)
    threshold = build_threshold(claims, observations, now)
    wwt = build_wwt(claims, observations, now)

    state_counts = {state: 0 for state in STATES}
    for claim in claims:
        state_counts[claim["state"]] += 1
    source_summary = _source_summary(catalog, health)
    active_claims = [claim for claim in claims if claim.get("state") in ACTIVE_STATES and now - parse_time(claim.get("material_time")) <= dt.timedelta(days=7)]
    situation = _situation_label(len(active_claims), source_summary["coverage_percent"])
    failures = [row for row in health if row.get("status") in ("failed", "empty", "stale")]

    catalog_by_id = {source["id"]: source for source in catalog.get("sources", [])}
    registry_rows = []
    for row in health:
        merged = dict(catalog_by_id.get(row["id"], {}))
        merged.update(row)
        registry_rows.append(merged)
    status = {
        "engine": "Y&Y Intelligence Engine",
        "version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "last_poll": iso_z(now),
        "poll_mode": "OFFLINE REANALYSIS" if offline else "LIVE COLLECTION",
        "mode": "AUTONOMOUS" if source_summary["coverage_percent"] >= 80 else "DEGRADED" if source_summary["coverage_percent"] >= 55 else "CRITICAL",
        "situation": situation,
        "quiet_interpretation": (
            "Few active claims with adequate collection coverage." if situation == "QUIET WITH COVERAGE"
            else "Insufficient source coverage prevents a reliable quiet assessment." if "GAP" in situation and not active_claims
            else "Active reporting is present; inspect source gaps before interpreting absence in uncovered domains."
        ),
        "sources_total": source_summary["enabled"],
        "sources_ok": source_summary["healthy_or_quiet"],
        "sources_failed": source_summary["failed"],
        "source_health_percent": source_summary["coverage_percent"],
        "source_diagnostics": source_summary,
        "source_status": health,
        "fetched_items": len(items),
        "new_observations": new_observations,
        "future_dated_items_rejected": future_rejected,
        "observation_count": len(observations),
        "claim_count": len(claims),
        "active_claim_count": len(active_claims),
        "claim_status_counts": state_counts,
        "confidence_distribution": confidence_distribution(claims),
        "anomaly_count": len(anomalies),
        "historical_memory_count": len(memory),
        "update_frequency_minutes": 30,
        "collection_blind_spots": [
            {"source": row.get("name"), "status": row.get("status"), "error": row.get("error")}
            for row in failures
        ],
        "chatgpt_dependency": False,
        "principle": catalog.get("policy"),
        "notes": [
            "Confidence and severity are separate; a consequential rumor can receive high watch priority without becoming fact.",
            "Discovery pointers do not count as independent confirmation until their publisher is resolved and assessed.",
            "Claims, weak signals, refutations, and dormant records remain preserved for lifecycle and pattern analysis.",
        ],
    }

    strategic_claims = [
        claim for claim in claims
        if claim.get("watch_priority", 0) >= 24 or claim.get("state") in ("CONFIRMED", "REFUTED")
    ][:250]
    atlas_claims = [
        claim for claim in strategic_claims
        if any(next((row for row in observations if row["id"] == oid and row.get("lat") is not None), None) for oid in claim.get("observation_ids", []))
    ][:200]
    infra_claims = [claim for claim in strategic_claims if set(claim.get("domains", [])) & {"INFRA", "CYBER", "ECONOMIC", "CLIMATE", "SPACE"}][:200]
    trafficking_claims = [claim for claim in strategic_claims if "TRAFFICKING" in claim.get("domains", [])][:200]
    live_observations = [row for row in observations if now - parse_time(row.get("published")) <= dt.timedelta(days=30)][:1200]

    write_json(data / "source-registry.json", {"generated_at": iso_z(now), "catalog_version": catalog.get("version"), "sources": registry_rows})
    write_json(data / "observations.json", {"generated_at": iso_z(now), "observations": observations})
    write_json(data / "claims.json", {"generated_at": iso_z(now), "states": list(STATES), "claims": claims})
    write_json(data / "historical-memory.json", {"generated_at": iso_z(now), "retention_policy": "retained until explicit reviewed removal", "claims": memory})
    write_json(data / "audit-log.json", {"generated_at": iso_z(now), "records": audit_log(claims, now)})
    write_json(data / "anomalies.json", {"generated_at": iso_z(now), "anomalies": anomalies})
    write_json(data / "autonomy-status.json", status)
    write_json(data / "live-events.json", {"generated_at": iso_z(now), "events": live_observations})
    write_json(data / "worldwatch-live.json", {"generated_at": iso_z(now), "claims": strategic_claims, "state_counts": state_counts})
    write_json(data / "atlas-live.json", {"generated_at": iso_z(now), "claims": atlas_claims})
    write_json(data / "infrawatch-live.json", {"generated_at": iso_z(now), "claims": infra_claims})
    write_json(data / "trfk-live.json", {"generated_at": iso_z(now), "claims": trafficking_claims})
    write_json(data / "threshold-live.json", threshold)
    write_json(data / "wwt-live.json", wwt)
    write_json(data / "brief-live.json", {
        "generated_at": iso_z(now),
        "top_claims": strategic_claims[:20],
        "state_counts": state_counts,
        "domain_counts": dict(collections.Counter(domain for claim in active_claims for domain in claim.get("domains", []))),
        "note": "Layered machine brief: every item retains its explicit claim state and confidence.",
    })
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Y&Y layered intelligence engine")
    parser.add_argument("--offline", action="store_true", help="reanalyze preserved observations without network collection")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    status = run(args.root, args.offline)
    counts = status["claim_status_counts"]
    print(
        f"Y&Y v{status['version']} {status['poll_mode']}: {status['source_health_percent']}% coverage; "
        f"{status['new_observations']} new observations; {status['claim_count']} claims; "
        + ", ".join(f"{state}={counts[state]}" for state in STATES)
    )
    for gap in status["collection_blind_spots"]:
        print(f"WARN {gap['source']}: {gap['status']} // {gap.get('error') or 'no current items'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
