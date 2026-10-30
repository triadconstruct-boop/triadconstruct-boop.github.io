"""Geographic presentation for WORLDWATCH; evidence and scores are unchanged."""
from __future__ import annotations

import collections
import re


# These are browsing desks, not claims about where an incident occurred.
# Headline geography takes precedence over incidental country mentions in evidence.
REGIONS = (
    ("europe-eurasia", "Europe & Eurasia", r"ukrain\w*|russia\w*|kyiv|kiev|moscow|kremlin|putin|zelensk\w*|nato|baltic\w*|europe\w*|german\w*|france|french|britain|british|united kingdom|poland|polish|belarus\w*|moldova\w*|tbilisi|armenia\w*|azerbaijan\w*|oleshky|alyoshki|ital\w*|spain|spanish|portug\w*|netherlands|dutch|belgi\w*|swed\w*|norw\w*|finland|finnish|denmark|danish|romania\w*|bulgaria\w*|greece|greek|serbi\w*|kosov\w*|croati\w*|hungar\w*|slovak\w*|czech\w*|estonia\w*|latvia\w*|lithuania\w*"),
    ("middle-east-north-africa", "Middle East & North Africa", r"iran\w*|israel\w*|palestin\w*|gaza|hamas|hezbollah|hormuz|persian gulf|saudi\w*|emirati|uae|qatar\w*|oman\w*|kuwait\w*|bahrain\w*|yemen\w*|houthi\w*|red sea|syria\w*|iraq\w*|leban\w*|jordan\w*|egypt\w*|libya\w*|algeri\w*|tunisi\w*|morocc\w*|turk\w*|türki\w*"),
    ("sub-saharan-africa", "Sub-Saharan Africa", r"sudan\w*|sahel|mali|niger|nigerian?\w*|burkina faso|chad|somali\w*|ethiopi\w*|eritrea\w*|congo\w*|rwanda\w*|uganda\w*|kenya\w*|mozambiqu\w*|south africa\w*|senegal\w*|cameroon\w*|zimbabw\w*|africa\w*"),
    ("east-asia-pacific", "East Asia & Pacific", r"china|chinese|beijing|taiwan\w*|taipei|south china sea|philippin\w*|japan\w*|tokyo|korea\w*|pyongyang|seoul|vietnam\w*|myanmar|burma|thailand|thai|cambodia\w*|laos|indonesia\w*|malaysia\w*|singapore\w*|australia\w*|new zealand|pacific|fiji|papua new guinea|solomon islands"),
    ("south-central-asia", "South & Central Asia", r"india(?:n|ns)?|pakistan\w*|afghan\w*|kabul|taliban|bangladesh\w*|nepal\w*|bhutan\w*|sri lanka\w*|maldiv\w*|kashmir|kazakh\w*|uzbek\w*|tajik\w*|kyrgyz\w*|turkmen\w*|central asia"),
    ("north-america", "North America", r"united states|u\.s\.|(?-i:US)|american\w*|canada|canadian\w*|washington|pentagon|white house|trump|congress|alaska\w*|california\w*|texas|new york"),
    ("latin-america-caribbean", "Latin America & Caribbean", r"latin america|caribbean|mexic\w*|brazil\w*|colombi\w*|venezuel\w*|ecuador\w*|peru\w*|bolivia\w*|chile\w*|argentin\w*|haiti\w*|cuba\w*|jamaica\w*|guatemala\w*|hondur\w*|el salvador|nicaragua\w*|costa rica\w*|panama\w*|dominican\w*"),
    ("global", "Global & Cross-border", ""),
)

LEGACY_REGIONS = {
    "RUSSIA": "europe-eurasia", "UKRAINE": "europe-eurasia", "EUROPE": "europe-eurasia",
    "IRAN": "middle-east-north-africa", "ISRAEL/PALESTINE": "middle-east-north-africa", "MIDDLE EAST": "middle-east-north-africa",
    "AFRICA": "sub-saharan-africa", "CHINA": "east-asia-pacific", "TAIWAN": "east-asia-pacific",
    "KOREAN PENINSULA": "east-asia-pacific", "INDO-PACIFIC": "east-asia-pacific",
    "UNITED STATES": "north-america", "LATIN AMERICA": "latin-america-caribbean",
}

CONFLICTS = (
    ("russia-ukraine", "Russia / Ukraine", "europe-eurasia", r"russia\w*|ukrain\w*|putin|zelensk\w*|kyiv|kiev|moscow|kremlin|oleshky|alyoshki"),
    ("european-security", "NATO / European security", "europe-eurasia", r"nato|baltic\w*|europe\w*|poland|polish|german\w*|belarus\w*"),
    ("israel-palestine", "Israel / Palestine", "middle-east-north-africa", r"israel\w*|palestin\w*|gaza|hamas|west bank"),
    ("iran-gulf", "Iran / Gulf", "middle-east-north-africa", r"iran\w*|hormuz|persian gulf|saudi\w*|qatar\w*|uae|emirati|bahrain\w*|kuwait\w*|oman\w*"),
    ("yemen-red-sea", "Yemen / Red Sea", "middle-east-north-africa", r"yemen\w*|houthi\w*|red sea"),
    ("syria-iraq-lebanon", "Syria / Iraq / Lebanon", "middle-east-north-africa", r"syria\w*|iraq\w*|leban\w*|hezbollah"),
    ("sudan", "Sudan", "sub-saharan-africa", r"sudan\w*|darfur|khartoum|el fasher"),
    ("sahel", "Sahel", "sub-saharan-africa", r"sahel|mali|niger|burkina faso|chad"),
    ("great-lakes", "Congo / Great Lakes", "sub-saharan-africa", r"congo\w*|rwanda\w*|uganda\w*|m23"),
    ("horn-of-africa", "Horn of Africa", "sub-saharan-africa", r"somali\w*|ethiopi\w*|eritrea\w*|al.shabaab"),
    ("taiwan-south-china-sea", "Taiwan / South China Sea", "east-asia-pacific", r"taiwan\w*|taipei|south china sea|philippin\w*"),
    ("korean-peninsula", "Korean Peninsula", "east-asia-pacific", r"korea\w*|pyongyang|seoul"),
    ("myanmar", "Myanmar", "east-asia-pacific", r"myanmar|burma"),
    ("afghanistan-pakistan", "Afghanistan / Pakistan", "south-central-asia", r"afghan\w*|kabul|taliban|pakistan\w*"),
    ("india-pakistan", "India / Pakistan / Kashmir", "south-central-asia", r"india(?:n|ns)?|pakistan\w*|kashmir"),
    ("mexico-security", "Mexico / organized crime", "latin-america-caribbean", r"mexic\w*|cartel\w*"),
    ("haiti", "Haiti", "latin-america-caribbean", r"haiti\w*"),
    ("venezuela", "Venezuela", "latin-america-caribbean", r"venezuel\w*"),
)


def _match(pattern: str, text: str):
    return re.search(r"(?<![\w])(?:" + pattern + r")(?![\w])", text, re.I) if pattern else None


def geography(claim: dict) -> dict:
    title = str(claim.get("headline", ""))
    title = re.sub(r"\bnew mexico\b", "US state", title, flags=re.I)
    # Do not treat every item in a multi-country daily briefing as occurring in
    # the first country mentioned in its long evidence list.
    hits = [(rid, match.start()) for rid, _, pattern in REGIONS if (match := _match(pattern, title))]
    conflicts = [cid for cid, _, _, pattern in CONFLICTS if _match(pattern, title)]
    if hits:
        primary = min(hits, key=lambda row: row[1])[0]
        regions = {rid for rid, _ in hits}
    else:
        regions = {LEGACY_REGIONS[tag] for tag in claim.get("regions", []) if tag in LEGACY_REGIONS}
        # Ambiguous multi-region records belong in the global overview desk.
        primary = next(iter(regions)) if len(regions) == 1 else "global"
    regions = regions or {"global"}
    regions.add(primary)
    conflict_regions = {rid for cid, _, rid, _ in CONFLICTS if cid in conflicts}
    # A foreign official's statement about an identified conflict is allocated
    # to that conflict's desk, rather than taking a second overview slot at home.
    if len(conflict_regions) == 1:
        primary = next(iter(conflict_regions))
        regions.add(primary)
    for cid, _, rid, _ in CONFLICTS:
        if cid in conflicts:
            regions.add(rid)
    return {
        "primary_region": primary,
        "regions": [rid for rid, _, _ in REGIONS if rid in regions],
        "conflicts": conflicts,
    }


def _rotate(buckets: dict[str, list[dict]], limit: int) -> list[dict]:
    queues = [collections.deque(rows) for rows in buckets.values() if rows]
    result = []
    while queues and len(result) < limit:
        for queue in queues:
            if queue and len(result) < limit:
                result.append(queue.popleft())
        queues = [queue for queue in queues if queue]
    return result


def build_worldwatch(ranked_claims: list[dict], generated_at: str, state_counts: dict, limit: int = 250) -> dict:
    """Reserve regional coverage before truncating; retain existing rank in views.

    A claim receives exactly one allocation desk, even when it mentions several
    regions. Conflict/topic rotation also keeps a small regional conflict from
    disappearing behind a larger conflict in the same desk. No score is edited.
    """
    annotated = [{**claim, "worldwatch": geography(claim)} for claim in ranked_claims]
    regional = {rid: [] for rid, _, _ in REGIONS}
    for claim in annotated:
        regional[claim["worldwatch"]["primary_region"]].append(claim)
    diversified = {}
    for rid, rows in regional.items():
        topics: dict[str, list[dict]] = {}
        for claim in rows:
            local_conflicts = [cid for cid, _, parent, _ in CONFLICTS if parent == rid and cid in claim["worldwatch"]["conflicts"]]
            topic = local_conflicts[0] if local_conflicts else (claim.get("domains") or ["SECURITY"])[0]
            topics.setdefault(topic, []).append(claim)
        diversified[rid] = _rotate(topics, len(rows))
    selected_ids = {claim["id"] for claim in _rotate(diversified, limit)}
    selected = [claim for claim in annotated if claim["id"] in selected_ids]
    desks = []
    for rid, label, _ in REGIONS:
        rows = [claim for claim in selected if rid in claim["worldwatch"]["regions"]]
        desks.append({
            "id": rid, "label": label, "count": len(rows),
            "conflicts": [
                {"id": cid, "label": name, "count": sum(cid in claim["worldwatch"]["conflicts"] for claim in rows)}
                for cid, name, parent, _ in CONFLICTS if parent == rid
            ],
        })
    return {
        "generated_at": generated_at, "claims": selected, "state_counts": state_counts,
        "geography": {"version": 1, "overview_limit": 24, "regions": desks, "candidate_count": len(annotated)},
    }
