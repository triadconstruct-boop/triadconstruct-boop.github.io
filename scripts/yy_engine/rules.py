from __future__ import annotations

import re

SOURCE_CLASS_PRIOR = {
    "primary_official": 0.94,
    "wire": 0.91,
    "established_media": 0.82,
    "specialist": 0.80,
    "regional_local": 0.70,
    "osint": 0.76,
    "expert": 0.79,
    "state_media": 0.49,
    "low_confidence": 0.38,
    "discovery": 0.18,
}

EVIDENCE_PRIOR = {
    "sensor_data": 0.98,
    "legal_record": 0.97,
    "official_data": 0.95,
    "official_statement": 0.86,
    "reported_fact": 0.79,
    "institutional_report": 0.82,
    "regional_report": 0.67,
    "specialist_report": 0.73,
    "osint_analysis": 0.68,
    "expert_analysis": 0.64,
    "press_release": 0.56,
    "state_media_claim": 0.40,
    "user_submitted_claim": 0.24,
    "discovery_pointer": 0.10,
}

DOMAIN_TERMS = {
    "WAR": ("airstrike", "air strike", "missile", "troops", "military", "invasion", "artillery", "ceasefire", "combat", "naval", "armed forces", "drone strike", "mobilization", "mobilisation"),
    "CYBER": ("cyber", "malware", "ransomware", "zero-day", "zero day", "exploit", "botnet", "ddos", "data breach", "intrusion", "hackers"),
    "INFRA": ("power grid", "pipeline", "railway", "railroad", "port", "subsea cable", "undersea cable", "water system", "telecommunications", "refinery", "airport", "dam", "critical infrastructure"),
    "NUCLEAR": ("nuclear", "uranium", "plutonium", "reactor", "iaea", "enrichment", "radiological", "warhead", "atomic"),
    "ECONOMIC": ("sanction", "tariff", "export control", "embargo", "shipping disruption", "supply chain", "asset freeze", "financial restriction", "energy price"),
    "POLITICAL": ("coup", "election", "government collapse", "martial law", "state of emergency", "constitutional crisis", "protest", "unrest", "diplomatic"),
    "TERRORISM": ("terror", "isis", "isil", "al-qaeda", "al qaeda", "extremist", "bomb plot", "attack plot", "mass casualty"),
    "TRAFFICKING": ("human trafficking", "sex trafficking", "labor trafficking", "labour trafficking", "forced labor", "forced labour", "modern slavery", "trafficking network", "exploitation ring"),
    "BIO": ("outbreak", "pathogen", "pandemic", "biosecurity", "biosafety", "biological", "public health emergency", "zoonotic", "epidemic"),
    "SPACE": ("satellite", "orbital", "space force", "anti-satellite", "asat", "spacecraft", "launch vehicle"),
    "CLIMATE": ("earthquake", "tsunami", "hurricane", "tornado", "wildfire", "flood", "cyclone", "storm surge", "extreme weather"),
    "HUMANITARIAN": ("refugee", "displaced", "humanitarian", "famine", "food insecurity", "aid convoy", "civilian casualties"),
}

REGIONS = {
    "UNITED STATES": (("united states", "u.s.", "u.s ", "american", "pentagon", "washington dc", "homeland"), (39.8283, -98.5795)),
    "RUSSIA": (("russia", "russian", "moscow", "kremlin"), (61.5240, 105.3188)),
    "UKRAINE": (("ukraine", "ukrainian", "kyiv", "odesa", "kharkiv"), (48.3794, 31.1656)),
    "CHINA": (("china", "chinese", "beijing", " prc "), (35.8617, 104.1954)),
    "TAIWAN": (("taiwan", "taiwanese", "taipei"), (23.6978, 120.9605)),
    "ISRAEL/PALESTINE": (("israel", "israeli", "gaza", "west bank", "jerusalem", "hamas"), (31.5, 34.8)),
    "IRAN": (("iran", "iranian", "tehran", "hormuz", "persian gulf"), (32.4279, 53.6880)),
    "KOREAN PENINSULA": (("north korea", "south korea", "pyongyang", "seoul", "korean peninsula"), (37.5, 127.5)),
    "EUROPE": (("european union", " europe ", " nato ", "baltic", "poland", "germany", "france"), (54.5260, 15.2551)),
    "MIDDLE EAST": (("middle east", "iraq", "syria", "lebanon", "jordan", "yemen", "red sea"), (29.2985, 42.5510)),
    "AFRICA": ((" africa ", "sahel", "sudan", "somalia", "congo", "ethiopia", "nigeria"), (1.6508, 17.6791)),
    "INDO-PACIFIC": (("indo-pacific", "south china sea", "philippines", "japan", "okinawa"), (15.0, 125.0)),
    "LATIN AMERICA": (("latin america", "mexico", "brazil", "venezuela", "colombia", "argentina"), (-8.8, -55.5)),
}

ACTORS = {
    "UNITED STATES": ("united states", "u.s.", "american", "pentagon", "white house"),
    "RUSSIA": ("russia", "russian", "kremlin", "moscow"),
    "CHINA": ("china", "chinese", "beijing", " prc "),
    "UKRAINE": ("ukraine", "ukrainian", "kyiv"),
    "IRAN": ("iran", "iranian", "tehran", "irgc"),
    "ISRAEL": ("israel", "israeli", "idf"),
    "NATO": ("nato", "alliance forces"),
    "EUROPEAN UNION": ("european union", "eu commission", "eu council"),
    "NORTH KOREA": ("north korea", "pyongyang", "dprk"),
    "ISIS": ("isis", "isil", "islamic state"),
    "AL-QAEDA": ("al-qaeda", "al qaeda"),
    "HAMAS": ("hamas",),
    "HEZBOLLAH": ("hezbollah",),
}

SPECULATION_MARKERS = ("may ", "might ", "could ", "possibly", "potentially", "speculat", "scenario", "reportedly", "unconfirmed", "sources say", "considering")
WARNING_MARKERS = ("warning", "alert", "buildup", "build-up", "prepar", "mobiliz", "evacuat", "heightened", "imminent", "threat", "indicators", "exercise", "surge")
ALLEGATION_MARKERS = ("alleged", "claims that", "accused", "according to unnamed", "purported", "unverified", "rumor", "rumour")
REFUTATION_MARKERS = ("false claim", "debunk", "denied", "refuted", "no evidence", "did not happen", "fabricated", "hoax", "misleading")
HIGH_IMPACT = ("nuclear weapon", "ballistic missile", "invasion", "airstrike", "state-sponsored", "critical infrastructure", "terrorist attack", "power grid", "chemical weapon", "biological weapon", "military clash", "major earthquake", "tsunami warning")
MEDIUM_IMPACT = ("sanction", "ransomware", "drone", "missile", "troops", "naval", "ceasefire", "export control", "trafficking network", "exploit", "earthquake", "hurricane", "tornado", "wildfire", "outbreak")

ATTRIBUTION_ROOTS = {
    "wire:reuters": ("according to reuters", "reuters reported", "reuters says"),
    "wire:ap": ("associated press reported", "according to the associated press", " ap reported"),
    "wire:afp": ("according to afp", "afp reported", "agence france-presse"),
    "official:anonymous": ("officials said", "official said", "unnamed official", "anonymous official", "sources familiar"),
}

HOMELAND_TERMS = ("united states", "u.s.", "american", "homeland", "u.s. soil", "us soil")
HOMELAND_PATHWAYS = ("critical infrastructure", "power grid", "water system", "pipeline", "airport", "port", "ransomware", "cyberattack", "terror plot", "bomb plot", "biological attack", "attack on", "inside the united states")
RETROSPECTIVE_MARKERS = ("anniversary", "years ago", "history of", "retrospective", "look back", "documentary")


def contains(text: str, term: str) -> bool:
    if term.startswith(" ") or term.endswith(" ") or len(term) < 4:
        return term in f" {text.lower()} "
    return term in text.lower()


def detect_domains(text: str, default: str = "SECURITY") -> list[str]:
    low = f" {text.lower()} "
    scored = [(domain, sum(1 for term in terms if term in low)) for domain, terms in DOMAIN_TERMS.items()]
    result = [domain for domain, score in sorted(scored, key=lambda item: item[1], reverse=True) if score]
    return result or [default]


def detect_regions(text: str) -> tuple[list[str], float | None, float | None]:
    low = f" {text.lower()} "
    found = [(region, coords) for region, (terms, coords) in REGIONS.items() if any(term in low for term in terms)]
    if not found:
        return ["GLOBAL"], None, None
    return [item[0] for item in found], found[0][1][0], found[0][1][1]


def detect_actors(text: str) -> list[str]:
    low = f" {text.lower()} "
    return [actor for actor, terms in ACTORS.items() if any(term in low for term in terms)]


def stance(text: str) -> str:
    low = f" {text.lower()} "
    if any(term in low for term in REFUTATION_MARKERS):
        return "refutation"
    if any(term in low for term in ALLEGATION_MARKERS):
        return "allegation"
    if any(term in low for term in WARNING_MARKERS):
        return "warning"
    if any(term in low for term in SPECULATION_MARKERS):
        return "speculation"
    return "report"


def specificity(text: str) -> float:
    low = text.lower()
    score = 0.30
    if re.search(r"\b\d{1,4}\b", low):
        score += 0.15
    if re.search(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|yesterday|tomorrow|january|february|march|april|may|june|july|august|september|october|november|december)\b", low):
        score += 0.15
    if detect_actors(low):
        score += 0.15
    if detect_regions(low)[0] != ["GLOBAL"]:
        score += 0.15
    if any(word in low for word in ("said", "announced", "confirmed", "filed", "recorded", "detected")):
        score += 0.10
    return min(1.0, score)


def attribution_root(text: str, fallback: str) -> str:
    low = f" {text.lower()} "
    for root, markers in ATTRIBUTION_ROOTS.items():
        if any(marker in low for marker in markers):
            return root
    return fallback


def impact_score(text: str, domains: list[str]) -> int:
    low = f" {text.lower()} "
    score = 20 + 10 * sum(term in low for term in HIGH_IMPACT) + 4 * sum(term in low for term in MEDIUM_IMPACT)
    score += 9 if set(domains) & {"WAR", "NUCLEAR", "TERRORISM"} else 6 if set(domains) & {"CYBER", "INFRA", "BIO"} else 2
    return max(0, min(100, score))
