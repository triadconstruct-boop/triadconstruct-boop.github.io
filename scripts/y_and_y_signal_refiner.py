#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RULES_VERSION = "2.2-evidence-gated"


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def iso_z(v):
    return v.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(v):
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
    except Exception:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def text(e):
    return f" {e.get('title','')} {e.get('summary','')} ".lower()


def any_term(s, terms):
    return any(t in s for t in terms)


def recent(events, hours):
    floor = now_utc() - dt.timedelta(hours=hours)
    ceiling = now_utc() + dt.timedelta(hours=2)
    return [e for e in events if floor <= parse_time(e.get("published")) <= ceiling]


def actor_count(s):
    groups = [
        ("US", (" united states ", " u.s. ", " american forces ", " us forces ")),
        ("RUSSIA", (" russia ", " russian forces ", " moscow ")),
        ("CHINA", (" china ", " chinese forces ", " beijing ", " prc ")),
        ("NATO", (" nato ", "allied forces", "alliance forces")),
    ]
    return sum(1 for _, terms in groups if any_term(s, terms))


COMBAT = ("attack", "attacked", "strike", "airstrike", "air strike", "missile", "combat", "clash", "engagement", "fired on", "intercepted", "hostilities")
ALLIANCE_TRIGGER = ("article 5", "collective defense", "collective defence", "mutual defense", "mutual defence", "defend an ally", "defend its ally", "treaty obligation", "allied deployment")
MULTI_THEATER_TRIGGER = ("second front", "multiple fronts", "multiple theaters", "multiple theatres", "multi-theater", "multi theatre", "simultaneous theaters", "simultaneous theatres", "two-front", "two front")
NUCLEAR_OBJECT = ("nuclear weapon", "nuclear weapons", "nuclear warhead", "nuclear warheads", "nuclear-capable missile", "nuclear capable missile", "strategic nuclear", "atomic weapon")
NUCLEAR_ACTION = ("launch", "test", "tested", "deploy", "deployed", "alert", "readiness", "strike", "threat", "threatened", "use of nuclear", "deterrent forces", "strategic forces", "warhead")
MOBILIZATION_TRIGGER = ("mobilization", "mobilisation", "mass call-up", "mass callup", "reservists called", "troop buildup", "troop build-up", "large-scale deployment", "large scale deployment", "carrier strike group deployed")
ECONOMIC_WAR_TRIGGER = ("sanctions", "export controls", "export control", "blockade", "embargo", "asset freeze", "financial restrictions", "shipping ban", "energy cutoff")
CRISIS_FAILURE_TRIGGER = ("talks collapse", "talks collapsed", "ceasefire collapse", "cease-fire collapse", "diplomatic breakdown", "negotiations suspended", "suspended talks", "withdrew from talks", "walked out of talks")
HYBRID_TRIGGER = ("state-sponsored", "state sponsored", "sabotage", "cyberattack", "cyber attack", "undersea cable", "subsea cable", "critical infrastructure attack", "infrastructure sabotage")


def vector_matches(e):
    s = text(e)
    matches = []
    if actor_count(s) >= 2 and any_term(s, COMBAT):
        matches.append("great_power_direct_clash")
    if any_term(s, ALLIANCE_TRIGGER):
        matches.append("alliance_entanglement")
    if any_term(s, MULTI_THEATER_TRIGGER) and any_term(s, COMBAT):
        matches.append("multi_theater_coupling")
    if any_term(s, NUCLEAR_OBJECT) and any_term(s, NUCLEAR_ACTION):
        matches.append("nuclear_escalation")
    if any_term(s, MOBILIZATION_TRIGGER):
        matches.append("military_mobilization")
    if any_term(s, ECONOMIC_WAR_TRIGGER):
        matches.append("economic_warfare")
    if any_term(s, CRISIS_FAILURE_TRIGGER):
        matches.append("crisis_control_failure")
    if any_term(s, HYBRID_TRIGGER) and any_term(s, ("state-sponsored", "state sponsored", "sabotage", "attack", "disruption")):
        matches.append("hybrid_preparation")
    return matches


def evidence_weight(e):
    sev = int(e.get("effective_severity", e.get("severity", 0)) or 0)
    authority = float(e.get("source_weight", 0.8) or 0.8)
    corroboration = max(1, int(e.get("corroboration_count", 1) or 1))
    score = 7 + max(0, sev - 50) * 0.45
    score *= min(1.15, 0.75 + authority * 0.3)
    score *= min(1.25, 1 + (corroboration - 1) * 0.08)
    return max(1, min(25, round(score)))


def refine_wwt(events):
    pool = [e for e in recent(events, 120) if int(e.get("effective_severity", e.get("severity", 0)) or 0) >= 45]
    vector_events = {k: [] for k in (
        "great_power_direct_clash", "alliance_entanglement", "multi_theater_coupling",
        "nuclear_escalation", "military_mobilization", "economic_warfare",
        "crisis_control_failure", "hybrid_preparation"
    )}
    event_match_count = {}
    for e in pool:
        matches = vector_matches(e)
        event_match_count[e.get("id")] = len(matches)
        for v in matches:
            vector_events[v].append(e)

    vectors = {v: min(100, sum(evidence_weight(e) for e in es)) for v, es in vector_events.items()}
    vals = list(vectors.values())
    highest = max(vals) if vals else 0
    average = round(sum(vals) / len(vals)) if vals else 0
    systemic = [
        e for e in pool
        if event_match_count.get(e.get("id"), 0) >= 2
        or (int(e.get("effective_severity", e.get("severity", 0)) or 0) >= 75 and event_match_count.get(e.get("id"), 0) >= 1)
    ]
    systemic_pressure = min(100, sum(max(3, evidence_weight(e) // 2) for e in systemic[:20]))
    score = round(highest * 0.40 + average * 0.35 + systemic_pressure * 0.25)
    top = sorted(
        {e.get("id"): e for es in vector_events.values() for e in es}.values(),
        key=lambda e: (int(e.get("effective_severity", e.get("severity", 0)) or 0), int(e.get("corroboration_count", 1) or 1), e.get("published", "")),
        reverse=True,
    )[:12]
    return {
        "generated_at": iso_z(now_utc()),
        "rules_version": RULES_VERSION,
        "score": score,
        "formula": "40% highest vector + 35% vector average + 25% systemic pressure",
        "highest_vector": highest,
        "vector_average": average,
        "systemic_pressure": systemic_pressure,
        "vectors": vectors,
        "vector_event_counts": {v: len(es) for v, es in vector_events.items()},
        "basis_event_count": len(systemic),
        "evidence_gate": "A vector activates only when an event satisfies vector-specific action conditions; topic words alone do not count.",
        "method": "Evidence-gated machine pressure index using authoritative public sources, action-specific vector rules, severity and corroboration.",
        "disclaimer": "Machine-generated public-source pressure signal only. It is not a statistically calibrated forecast of world war and does not replace the curated WWT assessment.",
        "top_events": top,
    }


US = (" united states ", " u.s. ", " american ", " america ", " homeland ", " us soil ", " u.s. soil ")
US_INFRA = ("u.s. infrastructure", "american infrastructure", "u.s. grid", "power grid", "water system", "telecommunications", "pipeline", "airport", "port")
ATTACK_ACTION = ("attack", "attacked", "strike", "bomb", "bombing", "missile", "sabotage", "assassination", "plot", "planned attack")
CYBER_ACTION = ("cyberattack", "cyber attack", "ransomware", "intrusion", "breach", "compromised", "state-sponsored", "state sponsored", "malware campaign")
TERROR_ACTION = ("terror plot", "terrorist attack", "bomb plot", "isis", "isil", "al-qaeda", "al qaeda", "domestic terrorism")
BIO_ACTION = ("biological attack", "bioterror", "pathogen attack", "deliberate release")


def homeland_gate(e):
    s = text(e)
    if not any_term(s, US):
        return None
    if any_term(s, TERROR_ACTION) and any_term(s, ATTACK_ACTION):
        return "terrorism"
    if any_term(s, CYBER_ACTION) and (any_term(s, US_INFRA) or " critical infrastructure " in s):
        return "cyber_infrastructure"
    if any_term(s, BIO_ACTION):
        return "biological"
    if any_term(s, ATTACK_ACTION) and any_term(s, ("military", "missile", "armed forces", "state actor", "foreign government")):
        return "state_attack"
    return None


def refine_threshold(events):
    candidates = []
    for e in recent(events, 96):
        pathway = homeland_gate(e)
        sev = int(e.get("effective_severity", e.get("severity", 0)) or 0)
        if pathway and sev >= 45:
            copy = dict(e)
            copy["threshold_pathway"] = pathway
            candidates.append(copy)
    candidates.sort(key=lambda e: (int(e.get("effective_severity", 0) or 0), int(e.get("corroboration_count", 1) or 1), e.get("published", "")), reverse=True)
    contributions = [evidence_weight(e) for e in candidates[:8]]
    score = min(100, round(sum(contributions) * 1.35)) if contributions else 0
    band = "HIGH SIGNAL" if score >= 75 else "ELEVATED SIGNAL" if score >= 55 else "WATCH SIGNAL" if score >= 30 else "BASELINE SIGNAL"
    return {
        "generated_at": iso_z(now_utc()),
        "rules_version": RULES_VERSION,
        "score": score,
        "band": band,
        "basis_event_count": len(candidates),
        "evidence_gate": "Requires both explicit U.S.-homeland relevance and a concrete attack, terror, cyber-infrastructure or biological pathway.",
        "method": "Evidence-gated public-source homeland signal weighted by severity, source authority and corroboration; not a probability.",
        "disclaimer": "Machine-generated public-source signal only. It is not a calibrated probability forecast and does not replace the curated THRESHOLD assessment.",
        "top_events": candidates[:12],
    }


def main():
    doc = load("live-events.json")
    events = doc.get("events", []) if isinstance(doc, dict) else []
    threshold = refine_threshold(events)
    wwt = refine_wwt(events)
    save("threshold-live.json", threshold)
    save("wwt-live.json", wwt)
    print(f"Y&Y signal refiner {RULES_VERSION}: THRESHOLD={threshold['score']} ({threshold['basis_event_count']} events); WWT={wwt['score']} ({wwt['basis_event_count']} systemic events)")


if __name__ == "__main__":
    main()
