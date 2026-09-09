from __future__ import annotations

import collections
import datetime as dt
import re
from typing import Iterable

from .rules import (
    EVIDENCE_PRIOR,
    HOMELAND_PATHWAYS,
    HOMELAND_TERMS,
    RETROSPECTIVE_MARKERS,
    SOURCE_CLASS_PRIOR,
    detect_actors,
    detect_domains,
    detect_regions,
    impact_score,
    stance,
)
from .util import canonical_url, clamp, iso_z, jaccard, parse_time, stable_id, tokens, utcnow

STATES = (
    "CONFIRMED",
    "CREDIBLE REPORT",
    "EARLY WARNING",
    "SPECULATIVE",
    "UNVERIFIED CLAIM",
    "REFUTED",
    "DORMANT",
)
ACTIVE_STATES = set(STATES) - {"REFUTED", "DORMANT"}
HARD_STATES = {"CONFIRMED", "CREDIBLE REPORT"}


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    low = f" {text.lower()} "
    return any(term in low for term in terms)


def _attribution_root(text: str, item: dict) -> str:
    low = f" {text.lower()} "
    patterns = {
        "wire:reuters": ("according to reuters", "reuters reported", "reuters says"),
        "wire:ap": ("associated press reported", "according to the associated press", " ap reported"),
        "wire:afp": ("according to afp", "afp reported", "agence france-presse"),
        "anonymous-official-chain": ("unnamed official", "anonymous official", "sources familiar with"),
    }
    for root, markers in patterns.items():
        if any(marker in low for marker in markers):
            return root
    if item.get("source_class") == "wire":
        return f"wire:{item.get('source_id', 'unknown')}"
    return str(item.get("ownership_root") or item.get("source_id") or "unknown")


def _specificity(text: str) -> float:
    """Estimate whether a report describes a concrete, falsifiable event."""
    low = text.lower()
    text_tokens = tokens(text)
    score = 0.25
    if any(char.isdigit() for char in text):
        score += 0.12
    if len(text_tokens) >= 8:
        score += 0.10
    if detect_actors(text):
        score += 0.16
    if detect_regions(text)[0] != ["GLOBAL"]:
        score += 0.15
    if _contains_any(low, ("said", "announced", "confirmed", "recorded", "detected", "filed", "published")):
        score += 0.13
    if _contains_any(low, ("today", "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")):
        score += 0.09
    return clamp(score, 0, 1)


def _has_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))


def _is_homeland_pathway(text: str, regions: list[str], domains: list[str]) -> bool:
    low = text.lower()
    us_explicit = "UNITED STATES" in regions or any(_has_phrase(low, term.strip()) for term in HOMELAND_TERMS)
    if not us_explicit or not set(domains) & {"WAR", "TERRORISM", "CYBER", "INFRA", "BIO", "NUCLEAR", "SECURITY"}:
        return False
    strict_domestic = any(_has_phrase(low, term) for term in ("u.s. soil", "us soil", "inside the united states", "in the united states", "across the united states", "homeland"))
    domestic_target = any(_has_phrase(low, term) for term in (
        "u.s. infrastructure", "american infrastructure", "u.s. power grid", "american power grid",
        "united states power grid", "american water system", "american water treatment", "american airport",
        "u.s. airport", "united states airport", "colonial pipeline",
    ))
    domestic_place = any(_has_phrase(low, term) for term in (
        "california", "texas", "florida", "new york", "washington state", "virginia", "pennsylvania",
        "ohio", "illinois", "georgia", "north carolina", "arizona", "michigan", "new jersey", "colorado",
    ))
    domestic_context = strict_domestic or domestic_target or domestic_place
    cyber_action = any(_has_phrase(low, term) for term in ("ransomware", "cyberattack", "cyber attack", "malware", "network intrusion"))
    infrastructure_target = any(_has_phrase(low, term) for term in ("critical infrastructure", "power grid", "water system", "water treatment", "pipeline", "airport", "seaport", "telecommunications"))
    terror_action = any(_has_phrase(low, term) for term in ("terror plot", "terrorist attack", "bomb plot", "terrorists may attack", "mass casualty attack"))
    biological_action = any(_has_phrase(low, term) for term in ("biological attack", "bioterror", "deliberate pathogen release"))
    kinetic_action = any(_has_phrase(low, term) for term in ("missile", "airstrike", "air strike", "armed attack", "strike against", "attack on"))
    return domestic_context and ((cyber_action and infrastructure_target) or terror_action or biological_action or kinetic_action)


def enrich_item(item: dict, now: dt.datetime | None = None, existing: dict | None = None) -> dict:
    now = now or utcnow()
    text = f"{item.get('title', '')} {item.get('summary', '')}"
    domains = detect_domains(text, item.get("default_domain") or item.get("domain") or "SECURITY")
    regions, lat, lon = detect_regions(text)
    if item.get("lat") is not None and item.get("lon") is not None:
        lat, lon = item["lat"], item["lon"]
    actors = detect_actors(text)
    source_class = item.get("source_class") or (
        "primary_official" if item.get("source_tier") == "primary" else "established_media"
    )
    reliability = float(item.get("source_reliability", item.get("source_weight", SOURCE_CLASS_PRIOR.get(source_class, 0.5))))
    evidence_type = item.get("evidence_type") or (
        "official_statement" if source_class == "primary_official" else "reported_fact"
    )
    published = item.get("published") or iso_z(now)
    url = canonical_url(item.get("url", ""))
    observation_id = item.get("id") or stable_id(item.get("source_id"), url, item.get("title"))
    first_seen = (existing or {}).get("first_seen") or item.get("first_seen") or iso_z(now)
    if item.get("published_inferred") and existing and existing.get("published"):
        published = existing["published"]
    marker_stance = stance(text)
    severity = impact_score(text, domains)
    sensor_significance = int(item.get("sensor_significance", 0) or 0)
    if sensor_significance >= 1000:
        severity += 18
    elif sensor_significance >= 600:
        severity += 12
    elif sensor_significance >= 400:
        severity += 7
    if item.get("tsunami"):
        severity += 8
    return {
        "id": observation_id,
        "title": item.get("title", "").strip(),
        "summary": item.get("summary", "").strip(),
        "url": url,
        "published": published,
        "published_inferred": bool(item.get("published_inferred")),
        "first_seen": first_seen,
        "last_seen": iso_z(now),
        "source": item.get("source") or item.get("source_id") or "Unknown",
        "source_id": item.get("source_id") or "unknown",
        "source_class": source_class,
        "source_reliability": round(clamp(reliability, 0, 1), 3),
        "evidence_type": evidence_type,
        "provenance_root": _attribution_root(text, item),
        "state_affiliated": bool(item.get("state_affiliated")),
        "discovered_via": item.get("discovered_via"),
        "discovery_only": bool(item.get("discovery_only")) or source_class == "discovery",
        "domains": domains,
        "domain": domains[0],
        "regions": regions,
        "region": regions[0],
        "actors": actors,
        "lat": lat,
        "lon": lon,
        "stance": marker_stance,
        "specificity": round(_specificity(text), 3),
        "severity": int(clamp(severity)),
        "homeland_pathway": _is_homeland_pathway(text, regions, domains),
        "retrospective": _contains_any(text, RETROSPECTIVE_MARKERS),
        "machine_generated": True,
    }


def _observation_item(value: dict) -> dict:
    """Migrate v2 events or reload v3 observations through the current rules."""
    result = dict(value)
    result.setdefault("source_class", "primary_official" if value.get("source_tier") == "primary" else "established_media")
    result.setdefault("source_reliability", value.get("source_weight", 0.7))
    result.setdefault("default_domain", value.get("domain", "SECURITY"))
    result.setdefault("evidence_type", "official_statement" if result["source_class"] == "primary_official" else "reported_fact")
    result.setdefault("ownership_root", value.get("provenance_root") or value.get("source_id"))
    return result


def merge_observations(items: list[dict], prior: list[dict], now: dt.datetime | None = None) -> tuple[list[dict], int, int]:
    now = now or utcnow()
    by_id: dict[str, dict] = {}
    for raw in prior:
        migrated = enrich_item(_observation_item(raw), now, raw)
        migrated["last_seen"] = raw.get("last_seen") or migrated["last_seen"]
        by_id[migrated["id"]] = migrated
    new_count = 0
    future_rejected = 0
    ceiling = now + dt.timedelta(hours=2)
    for item in items:
        provisional = enrich_item(item, now)
        if parse_time(provisional["published"]) > ceiling:
            future_rejected += 1
            continue
        existing = by_id.get(provisional["id"])
        observation = enrich_item(item, now, existing)
        if existing is None:
            new_count += 1
        by_id[observation["id"]] = observation
    observations = sorted(by_id.values(), key=lambda row: parse_time(row.get("published")), reverse=True)
    return observations, new_count, future_rejected


def _claim_similarity(observation: dict, claim: dict) -> float:
    left = tokens(f"{observation.get('title', '')} {observation.get('summary', '')}")
    right = set(claim.get("signature_tokens") or tokens(claim.get("headline", "")))
    overlap = jaccard(left, right)
    shared_domain = bool(set(observation.get("domains", [])) & set(claim.get("domains", [])))
    shared_region = bool((set(observation.get("regions", [])) - {"GLOBAL"}) & (set(claim.get("regions", [])) - {"GLOBAL"}))
    shared_actor = bool(set(observation.get("actors", [])) & set(claim.get("actors", [])))
    material = parse_time(claim.get("material_time") or claim.get("last_seen"))
    age_days = abs((parse_time(observation.get("published")) - material).total_seconds()) / 86400
    time_score = 1.0 if age_days <= 2 else 0.7 if age_days <= 7 else 0.25 if age_days <= 30 else 0
    return overlap * 0.62 + (0.12 if shared_domain else 0) + (0.10 if shared_region else 0) + (0.10 if shared_actor else 0) + time_score * 0.06


def _new_claim(observation: dict) -> dict:
    signature = sorted(tokens(observation.get("title", "")))[:12]
    return {
        "id": f"claim-{stable_id(observation['id'], *signature, length=18)}",
        "headline": observation.get("title") or "Untitled claim",
        "signature_tokens": signature,
        "observation_ids": [],
        "first_seen": observation.get("first_seen"),
        "last_seen": observation.get("last_seen"),
        "material_time": observation.get("published"),
        "domains": observation.get("domains", []),
        "regions": observation.get("regions", []),
        "actors": observation.get("actors", []),
    }


def _age_recency(material_time: str, now: dt.datetime) -> float:
    hours = max(0.0, (now - parse_time(material_time)).total_seconds() / 3600)
    if hours <= 6:
        return 100
    if hours <= 24:
        return 100 - (hours - 6) * 0.55
    if hours <= 72:
        return 90 - (hours - 24) * 0.31
    if hours <= 168:
        return 75 - (hours - 72) * 0.21
    if hours <= 336:
        return 55 - (hours - 168) * 0.15
    if hours <= 720:
        return 30 - (hours - 336) * 0.052
    return 8


def confidence_model(support: list[dict], contradiction: list[dict], material_time: str, now: dt.datetime) -> tuple[int, dict]:
    evidence = [row for row in support if not row.get("discovery_only")]
    roots = {row.get("provenance_root") for row in evidence if row.get("provenance_root")}
    source_values = [100 * float(row.get("source_reliability", 0.4)) for row in evidence]
    source_quality = sum(sorted(source_values, reverse=True)[:3]) / max(1, min(3, len(source_values))) if source_values else 15
    independence = min(100, 25 + max(0, len(roots) - 1) * 27)
    corroboration = min(100, 22 + max(0, len(roots) - 1) * 30 + max(0, len(evidence) - len(roots)) * 3)
    specificity = 100 * sum(float(row.get("specificity", 0.25)) for row in support) / max(1, len(support))
    recency = _age_recency(material_time, now)
    evidence_type = 100 * max((EVIDENCE_PRIOR.get(row.get("evidence_type"), 0.4) for row in evidence), default=0.12)
    historical_reliability = sum(source_values) / max(1, len(source_values)) if source_values else 20
    age_days = max(0, (now - parse_time(material_time)).total_seconds() / 86400)
    maturity = min(100, 24 + len(evidence) * 11 + min(age_days, 14) * 1.6)
    contradiction_roots = {row.get("provenance_root") for row in contradiction if row.get("provenance_root")}
    contradiction_quality = max((float(row.get("source_reliability", 0)) for row in contradiction), default=0)
    contradiction_penalty = min(100, len(contradiction_roots) * 32 + contradiction_quality * 45)
    components = {
        "source_quality": round(source_quality),
        "independence": round(independence),
        "corroboration": round(corroboration),
        "contradiction": round(contradiction_penalty),
        "specificity": round(specificity),
        "recency": round(recency),
        "evidence_type": round(evidence_type),
        "historical_reliability": round(historical_reliability),
        "claim_maturity": round(maturity),
    }
    score = (
        source_quality * 0.23 + independence * 0.16 + corroboration * 0.14 + specificity * 0.12
        + recency * 0.12 + evidence_type * 0.10 + historical_reliability * 0.08 + maturity * 0.05
        - contradiction_penalty * 0.35
    )
    return round(clamp(score)), components


def classify_claim(support: list[dict], contradiction: list[dict], confidence: int, material_time: str, now: dt.datetime) -> tuple[str, str]:
    age_hours = max(0, (now - parse_time(material_time)).total_seconds() / 3600)
    credible_contradiction = [row for row in contradiction if row.get("source_reliability", 0) >= 0.72 and not row.get("discovery_only")]
    credible_support = [row for row in support if row.get("source_reliability", 0) >= 0.65 and not row.get("discovery_only")]
    if credible_contradiction and (not credible_support or (len({r.get('provenance_root') for r in credible_contradiction}) >= 2 and len(credible_support) <= 1)):
        return "REFUTED", "Credible refuting evidence outweighs or stands without credible supporting evidence."
    if age_hours > 336:
        return "DORMANT", "No material evidence arrived within the 14-day active window; the claim remains preserved."
    direct = any(row.get("evidence_type") in ("sensor_data", "legal_record", "official_data") and row.get("source_class") == "primary_official" for row in support)
    roots = {row.get("provenance_root") for row in credible_support}
    speculative = any(row.get("stance") in ("speculation", "allegation") for row in support)
    warning = any(row.get("stance") == "warning" for row in support)
    if not speculative and ((direct and confidence >= 65) or (len(roots) >= 2 and confidence >= 73)):
        return "CONFIRMED", "Direct authoritative evidence or at least two independent credible provenance roots clears the confirmation gate."
    if confidence >= 61 and credible_support:
        return "CREDIBLE REPORT", "Credible sourcing clears the reporting threshold but the confirmation gate is not yet met."
    if warning and confidence >= 34:
        return "EARLY WARNING", "Preparatory, warning, or escalation indicators merit watch priority before hard confirmation."
    if speculative and confidence >= 25:
        return "SPECULATIVE", "The claim is explicitly conditional, alleged, or speculative and remains labeled as such."
    return "UNVERIFIED CLAIM", "Available reporting does not yet clear the credible-report or confirmation threshold."


def _branches(claim: dict, contradiction: list[dict]) -> dict:
    domain_text = "/".join(claim.get("domains", [])[:3]) or "SECURITY"
    actor_text = ", ".join(claim.get("actors", [])[:3]) or "the reported actors"
    return {
        "current_observation": claim.get("headline"),
        "plausible_explanations": [
            f"A genuine {domain_text} development involving {actor_text} is unfolding as reported.",
            "Routine, defensive, coercive, or signaling activity is being interpreted as escalation.",
            "Incomplete sourcing, recycled attribution, or information operations are distorting the picture.",
        ],
        "escalation_branch": f"Related {domain_text} indicators spread, become operational, or draw additional actors into the event.",
        "de_escalation_branch": "Independent evidence fails to appear, activity reverses, or authoritative clarification narrows the claim.",
        "confirm_indicators": [
            "A primary record, sensor observation, or on-record official confirmation.",
            "Matching detail from a genuinely independent provenance root.",
            "Observable follow-on action consistent with the reported event.",
        ],
        "falsify_indicators": [
            "Time-stamped primary evidence incompatible with the claim.",
            "Independent, technically specific refutation from credible sources.",
            "Predicted follow-on indicators fail to occur inside the stated window.",
        ],
        "contradictory_evidence_present": bool(contradiction),
    }


def _score_claim(claim: dict, support: list[dict]) -> tuple[int, int]:
    if claim["state"] == "REFUTED":
        return 0, 0
    severity = max((int(row.get("severity", 0)) for row in support), default=0)
    confidence = claim["confidence"]
    threat_factors = {
        "CONFIRMED": 1.0, "CREDIBLE REPORT": 0.72, "EARLY WARNING": 0.33,
        "SPECULATIVE": 0.16, "UNVERIFIED CLAIM": 0.10, "DORMANT": 0.04,
    }
    threat = round(severity * (confidence / 100) * threat_factors.get(claim["state"], 0))
    weak_bonus = 20 if claim["state"] == "EARLY WARNING" else 12 if claim["state"] == "SPECULATIVE" else 7 if claim["state"] == "UNVERIFIED CLAIM" else 0
    convergence = min(15, max(0, len(claim.get("domains", [])) - 1) * 6 + max(0, len(claim.get("actors", [])) - 1) * 2)
    watch = round(clamp(severity * (0.34 + confidence / 210) + weak_bonus + convergence))
    if claim["state"] == "DORMANT":
        watch = round(watch * 0.25)
    return threat, watch


def build_claims(observations: list[dict], prior_claims: list[dict], now: dt.datetime | None = None) -> list[dict]:
    now = now or utcnow()
    observation_by_id = {row["id"]: row for row in observations}
    claims: list[dict] = []
    assigned: set[str] = set()
    prior_by_id: dict[str, dict] = {}
    for old in prior_claims:
        ids = [oid for oid in old.get("observation_ids", []) if oid in observation_by_id and oid not in assigned]
        if not ids:
            continue
        base = dict(old)
        base["observation_ids"] = ids
        claims.append(base)
        prior_by_id[base["id"]] = old
        assigned.update(ids)
    for observation in sorted(observations, key=lambda row: parse_time(row.get("published"))):
        if observation["id"] in assigned:
            continue
        candidates = []
        for claim in claims:
            material = parse_time(claim.get("material_time") or claim.get("last_seen"))
            if abs((parse_time(observation.get("published")) - material).total_seconds()) > 35 * 86400:
                continue
            similarity = _claim_similarity(observation, claim)
            if similarity >= 0.47:
                candidates.append((similarity, claim))
        claim = max(candidates, key=lambda row: row[0])[1] if candidates else _new_claim(observation)
        if not candidates:
            claims.append(claim)
        claim.setdefault("observation_ids", []).append(observation["id"])
        assigned.add(observation["id"])

    for claim in claims:
        rows = [observation_by_id[oid] for oid in claim["observation_ids"]]
        support = [row for row in rows if row.get("stance") != "refutation"]
        contradiction = [row for row in rows if row.get("stance") == "refutation"]
        headline_pool = support or rows
        headline_pick = max(headline_pool, key=lambda row: (float(row.get("source_reliability", 0)), float(row.get("specificity", 0)), row.get("published", "")))
        material_time = max((row.get("published", "") for row in rows), default=claim.get("material_time"))
        confidence, components = confidence_model(support, contradiction, material_time, now)
        state, reason = classify_claim(support, contradiction, confidence, material_time, now)
        old = prior_by_id.get(claim["id"], {})
        old_confidence = old.get("confidence")
        direction = "NEW" if old_confidence is None else "UP" if confidence > old_confidence + 1 else "DOWN" if confidence < old_confidence - 1 else "STABLE"
        claim.update({
            "headline": headline_pick.get("title") or claim.get("headline"),
            "signature_tokens": sorted(tokens(headline_pick.get("title", "")))[:16],
            "first_seen": min((row.get("first_seen", row.get("published", "")) for row in rows), default=iso_z(now)),
            "last_seen": max((row.get("last_seen", "") for row in rows), default=iso_z(now)),
            "material_time": material_time,
            "state": state,
            "confidence": confidence,
            "confidence_direction": direction,
            "confidence_components": components,
            "classification_reason": reason,
            "domains": sorted({value for row in rows for value in row.get("domains", [])}),
            "regions": sorted({value for row in rows for value in row.get("regions", [])}),
            "actors": sorted({value for row in rows for value in row.get("actors", [])}),
            "supporting_observation_ids": [row["id"] for row in support],
            "contradictory_observation_ids": [row["id"] for row in contradiction],
            "source_count": len({row.get("source_id") for row in rows}),
            "independent_provenance_count": len({row.get("provenance_root") for row in support if not row.get("discovery_only")}),
            "sources": sorted({row.get("source") for row in rows if row.get("source")}),
            "provenance_roots": sorted({row.get("provenance_root") for row in rows if row.get("provenance_root")}),
            "evidence": [{
                "observation_id": row["id"], "title": row.get("title"), "source": row.get("source"),
                "source_class": row.get("source_class"), "provenance_root": row.get("provenance_root"),
                "stance": row.get("stance"), "published": row.get("published"), "url": row.get("url"),
                "discovery_only": row.get("discovery_only", False),
            } for row in sorted(rows, key=lambda value: value.get("published", ""), reverse=True)[:16]],
            "state_affiliated_reporting": any(row.get("state_affiliated") for row in rows),
            "discovery_only": bool(support) and all(row.get("discovery_only") for row in support),
            "branch_analysis": {},
            "historical_matches": [],
            "cross_domain_links": [],
            "anomaly_ids": [],
        })
        claim["branch_analysis"] = _branches(claim, contradiction)
        claim["threat_score"], claim["watch_priority"] = _score_claim(claim, support)
        claim["audit"] = {
            "reason": reason,
            "support_count": len(support),
            "contradiction_count": len(contradiction),
            "independent_roots": claim["independent_provenance_count"],
            "confidence_formula": "23% source + 16% independence + 14% corroboration + 12% specificity + 12% recency + 10% evidence type + 8% historical reliability + 5% maturity - 35% contradiction",
            "material_time_used_for_decay": material_time,
        }
    return sorted(claims, key=lambda row: (row.get("watch_priority", 0), row.get("material_time", "")), reverse=True)


def add_cross_domain_links(claims: list[dict], now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    active = [claim for claim in claims if claim.get("state") in ACTIVE_STATES and now - parse_time(claim.get("material_time")) <= dt.timedelta(hours=120)]
    for index, left in enumerate(active):
        links = []
        for right in active[index + 1:]:
            if set(left.get("domains", [])) == set(right.get("domains", [])):
                continue
            shared_actors = sorted(set(left.get("actors", [])) & set(right.get("actors", [])))
            shared_regions = sorted((set(left.get("regions", [])) & set(right.get("regions", []))) - {"GLOBAL"})
            if not shared_actors and not shared_regions:
                continue
            link = {
                "claim_id": right["id"],
                "shared_actors": shared_actors,
                "shared_regions": shared_regions,
                "domains": right.get("domains", []),
            }
            links.append(link)
            right.setdefault("cross_domain_links", []).append({
                "claim_id": left["id"], "shared_actors": shared_actors,
                "shared_regions": shared_regions, "domains": left.get("domains", []),
            })
        left["cross_domain_links"] = links[:12]


def detect_anomalies(claims: list[dict], now: dt.datetime | None = None) -> list[dict]:
    now = now or utcnow()
    pool = [claim for claim in claims if claim.get("state") in ACTIVE_STATES and now - parse_time(claim.get("material_time")) <= dt.timedelta(hours=96)]
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for claim in pool:
        keys = claim.get("actors") or [region for region in claim.get("regions", []) if region != "GLOBAL"]
        for key in keys:
            groups[key].append(claim)
    anomalies = []
    for key, members in groups.items():
        domains = sorted({domain for claim in members for domain in claim.get("domains", [])})
        roots = {root for claim in members for root in claim.get("provenance_roots", [])}
        if len(domains) < 2 or len(members) < 2:
            continue
        unusual = any(set(pair).issubset(domains) for pair in (("WAR", "CYBER"), ("WAR", "NUCLEAR"), ("CYBER", "INFRA"), ("BIO", "TRAFFICKING"), ("SPACE", "WAR")))
        if not unusual and len(domains) < 3:
            continue
        anomaly_id = f"anomaly-{stable_id(key, *domains, *(c['id'] for c in members[:8]), length=16)}"
        anomaly = {
            "id": anomaly_id,
            "subject": key,
            "domains": domains,
            "claim_ids": [claim["id"] for claim in members[:12]],
            "independent_provenance_count": len(roots),
            "priority": round(clamp(35 + len(domains) * 10 + len(roots) * 4)),
            "reason": "Unusual near-time convergence across normally separate domains; this is a watch cue, not proof of coordination.",
        }
        anomalies.append(anomaly)
        for claim in members:
            claim.setdefault("anomaly_ids", []).append(anomaly_id)
            claim["watch_priority"] = round(clamp(claim.get("watch_priority", 0) + min(8, len(domains) * 2)))
    return sorted(anomalies, key=lambda row: row["priority"], reverse=True)


def add_historical_matches(claims: list[dict], memory: list[dict], now: dt.datetime | None = None) -> None:
    now = now or utcnow()
    for claim in claims:
        if claim.get("state") not in ACTIVE_STATES:
            continue
        matches = []
        for historic in memory:
            if historic.get("id") == claim.get("id"):
                continue
            age = now - parse_time(historic.get("material_time"))
            if age < dt.timedelta(days=30) or age > dt.timedelta(days=365):
                continue
            domain_overlap = set(claim.get("domains", [])) & set(historic.get("domains", []))
            actor_overlap = set(claim.get("actors", [])) & set(historic.get("actors", []))
            region_overlap = (set(claim.get("regions", [])) & set(historic.get("regions", []))) - {"GLOBAL"}
            if domain_overlap and (actor_overlap or region_overlap):
                matches.append({
                    "claim_id": historic.get("id"),
                    "headline": historic.get("headline"),
                    "material_time": historic.get("material_time"),
                    "shared_domains": sorted(domain_overlap),
                    "shared_actors": sorted(actor_overlap),
                    "shared_regions": sorted(region_overlap),
                })
        claim["historical_matches"] = matches[:5]
        if matches:
            claim["watch_priority"] = round(clamp(claim.get("watch_priority", 0) + min(5, len(matches) * 2)))


def update_historical_memory(claims: list[dict], prior_memory: list[dict], now: dt.datetime | None = None) -> list[dict]:
    now = now or utcnow()
    by_id = {entry.get("id"): entry for entry in prior_memory if entry.get("id")}
    for claim in claims:
        by_id[claim["id"]] = {
            "id": claim["id"], "headline": claim.get("headline"), "material_time": claim.get("material_time"),
            "state": claim.get("state"), "domains": claim.get("domains", []), "regions": claim.get("regions", []),
            "actors": claim.get("actors", []), "peak_confidence": max(claim.get("confidence", 0), by_id.get(claim["id"], {}).get("peak_confidence", 0)),
            "peak_watch_priority": max(claim.get("watch_priority", 0), by_id.get(claim["id"], {}).get("peak_watch_priority", 0)),
            "last_evaluated": iso_z(now),
        }
    return sorted(by_id.values(), key=lambda row: row.get("material_time", ""), reverse=True)


def _claim_text(claim: dict, observations: dict[str, dict]) -> str:
    rows = [observations[oid] for oid in claim.get("observation_ids", []) if oid in observations]
    return " ".join([claim.get("headline", "")] + [f"{row.get('title', '')} {row.get('summary', '')}" for row in rows]).lower()


WWT_VECTORS = {
    "great_power_direct_clash": ("direct clash", "fired on", "airstrike", "naval clash", "military confrontation"),
    "alliance_entanglement": ("article 5", "collective defense", "collective defence", "treaty obligation", "defend an ally"),
    "multi_theater_coupling": ("second front", "multiple fronts", "multi-theater", "multi theatre", "simultaneously"),
    "nuclear_escalation": ("nuclear weapon", "nuclear warhead", "strategic forces", "nuclear-capable", "enrichment"),
    "military_mobilization": ("mobilization", "mobilisation", "reservists", "troop buildup", "carrier strike group"),
    "economic_warfare": ("sanctions", "export controls", "blockade", "embargo", "asset freeze", "shipping disruption"),
    "crisis_control_failure": ("talks collapse", "ceasefire collapse", "diplomatic breakdown", "negotiations suspended"),
    "hybrid_preparation": ("state-sponsored", "sabotage", "cyberattack", "undersea cable", "critical infrastructure attack"),
}


def _wwt_vector_matches(claim: dict, text: str) -> list[str]:
    matches = []
    great_powers = {"UNITED STATES", "RUSSIA", "CHINA", "NATO"} & set(claim.get("actors", []))
    if len(great_powers) >= 2 and _contains_any(text, WWT_VECTORS["great_power_direct_clash"]):
        matches.append("great_power_direct_clash")
    if _contains_any(text, WWT_VECTORS["alliance_entanglement"]):
        matches.append("alliance_entanglement")
    if _contains_any(text, WWT_VECTORS["multi_theater_coupling"]) and _contains_any(text, ("attack", "strike", "combat", "clash", "front")):
        matches.append("multi_theater_coupling")
    if _contains_any(text, WWT_VECTORS["nuclear_escalation"]) and _contains_any(text, ("weapon", "warhead", "launch", "deploy", "alert", "readiness", "strike", "threat", "enrichment")):
        matches.append("nuclear_escalation")
    for name in ("military_mobilization", "economic_warfare", "crisis_control_failure"):
        if _contains_any(text, WWT_VECTORS[name]):
            matches.append(name)
    if _contains_any(text, WWT_VECTORS["hybrid_preparation"]) and set(claim.get("domains", [])) & {"CYBER", "INFRA", "WAR"}:
        matches.append("hybrid_preparation")
    return matches


def _provenance_capped_score(claims: list[dict], metric: str, cap: int = 18) -> int:
    by_root: dict[str, int] = {}
    for claim in claims:
        contribution = min(cap, round(claim.get(metric, 0) * 0.24))
        roots = claim.get("provenance_roots") or [claim["id"]]
        root = roots[0]
        by_root[root] = max(by_root.get(root, 0), contribution)
    return round(clamp(sum(sorted(by_root.values(), reverse=True)[:10]) * 0.85))


def build_wwt(claims: list[dict], observations: list[dict], now: dt.datetime | None = None) -> dict:
    now = now or utcnow()
    observation_map = {row["id"]: row for row in observations}
    active = [claim for claim in claims if claim.get("state") in ACTIVE_STATES and now - parse_time(claim.get("material_time")) <= dt.timedelta(hours=120)]
    matches_by_claim = {claim["id"]: _wwt_vector_matches(claim, _claim_text(claim, observation_map)) for claim in active}
    qualified = [claim for claim in active if matches_by_claim[claim["id"]]]
    verified = [claim for claim in qualified if claim.get("state") in HARD_STATES]
    early = [claim for claim in qualified if claim.get("state") not in HARD_STATES and claim.get("watch_priority", 0) >= 35]
    vectors = {}
    vector_claim_counts = {}
    for name in WWT_VECTORS:
        matches = [claim for claim in qualified if name in matches_by_claim[claim["id"]]]
        vectors[name] = _provenance_capped_score(matches, "watch_priority", cap=16)
        vector_claim_counts[name] = len(matches)
    verified_score = _provenance_capped_score(verified, "threat_score")
    early_score = _provenance_capped_score(early, "watch_priority")
    return {
        "generated_at": iso_z(now),
        "rules_version": "3.0-layered-early-warning",
        "score": verified_score,
        "verified_pressure": {"score": verified_score, "claim_count": len(verified), "top_claims": verified[:12]},
        "early_warning_pressure": {"score": early_score, "claim_count": len(early), "top_claims": early[:12]},
        "vectors": vectors,
        "vector_claim_counts": vector_claim_counts,
        "formula": "Independent-provenance-capped claim contributions; verified and early-warning pressure remain separate.",
        "safeguard": "Republished stories sharing one provenance root cannot multiply pressure; speculative claims never enter Verified Pressure.",
        "disclaimer": "Machine-generated public-source warning indicators, not a probability of world war or an official warning.",
        "top_claims": (verified + early)[:16],
    }


def build_threshold(claims: list[dict], observations: list[dict], now: dt.datetime | None = None) -> dict:
    now = now or utcnow()
    observation_map = {row["id"]: row for row in observations}
    candidates = []
    for claim in claims:
        if claim.get("state") not in ACTIVE_STATES or now - parse_time(claim.get("material_time")) > dt.timedelta(hours=96):
            continue
        text = _claim_text(claim, observation_map)
        if _contains_any(text, RETROSPECTIVE_MARKERS):
            continue
        path = any(observation_map.get(oid, {}).get("homeland_pathway") for oid in claim.get("observation_ids", []))
        if path:
            candidates.append(claim)
    confirmed = [claim for claim in candidates if claim.get("state") == "CONFIRMED"]
    precursor = [claim for claim in candidates if claim.get("state") != "CONFIRMED"]
    confirmed_score = _provenance_capped_score(confirmed, "threat_score", cap=22)
    precursor_score = _provenance_capped_score(precursor, "watch_priority", cap=18)
    return {
        "generated_at": iso_z(now),
        "rules_version": "3.0-layered-early-warning",
        "score": confirmed_score,
        "confirmed_homeland_signal": {"score": confirmed_score, "claim_count": len(confirmed), "top_claims": confirmed[:12]},
        "precursor_speculative_signal": {"score": precursor_score, "claim_count": len(precursor), "top_claims": precursor[:12]},
        "evidence_gate": "Requires an explicit U.S. location or target and a concrete attack, terror, cyber-infrastructure, biological, or critical-infrastructure pathway; historical retrospectives are excluded.",
        "safeguard": "Credible, early-warning, speculative, and unverified material cannot enter Confirmed Homeland Signal.",
        "disclaimer": "Machine-generated public-source signal, not a calibrated probability or official homeland warning.",
        "top_claims": (confirmed + precursor)[:16],
    }


def audit_log(claims: list[dict], now: dt.datetime | None = None) -> list[dict]:
    now = now or utcnow()
    return [{
        "evaluated_at": iso_z(now), "claim_id": claim["id"], "state": claim["state"],
        "confidence": claim["confidence"], "confidence_direction": claim["confidence_direction"],
        "threat_score": claim["threat_score"], "watch_priority": claim["watch_priority"],
        "components": claim["confidence_components"], "reason": claim["classification_reason"],
        "supporting_observation_ids": claim["supporting_observation_ids"],
        "contradictory_observation_ids": claim["contradictory_observation_ids"],
    } for claim in claims]


def confidence_distribution(claims: list[dict]) -> dict:
    buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for claim in claims:
        score = int(claim.get("confidence", 0))
        key = "0-19" if score < 20 else "20-39" if score < 40 else "40-59" if score < 60 else "60-79" if score < 80 else "80-100"
        buckets[key] += 1
    return buckets
