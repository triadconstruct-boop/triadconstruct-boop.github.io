from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .rules import SOURCE_CLASS_PRIOR
from .util import clean, hostname, iso_z, parse_date, parse_time, utcnow

USER_AGENT = "YY-Intelligence-Engine/3.0 (+https://yyrv.net/system/)"
TIMEOUT_SECONDS = 14
MAX_ITEMS_PER_SOURCE = 160


def load_catalog(path: Path) -> dict:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    ids = [source["id"] for source in catalog.get("sources", [])]
    if len(ids) != len(set(ids)):
        raise ValueError("source catalog contains duplicate IDs")
    return catalog


def _fetch_bytes(url: str, retries: int = 1) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/rss+xml, application/atom+xml, application/json, application/geo+json, text/xml, */*",
                },
            )
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read()
        except Exception as exc:  # isolated per source and reported in diagnostics
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                break
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _node_text(node: ET.Element, names: tuple[str, ...]) -> str:
    wanted = set(names)
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1].lower() in wanted and child.text:
            return child.text.strip()
    return ""


def _base_item(source: dict, title: str, summary: str, url: str, published: object, **extra) -> dict:
    observed = utcnow()
    published_at, inferred = parse_date(published, observed)
    item = {
        "title": clean(title, 500),
        "summary": clean(summary, 1800),
        "url": url,
        "published": published_at,
        "published_inferred": inferred,
        "source_id": source["id"],
        "source": source["name"],
        "source_class": source["source_class"],
        "source_reliability": float(source.get("reliability", SOURCE_CLASS_PRIOR.get(source["source_class"], 0.5))),
        "default_domain": source.get("default_domain", "SECURITY"),
        "evidence_type": source.get("evidence_type", "reported_fact"),
        "ownership_root": source.get("ownership_root") or source["id"],
        "state_affiliated": bool(source.get("state_affiliated")),
        "discovered_via": source.get("aggregated_by"),
        "discovery_only": bool(source.get("discovery_only")),
    }
    item.update(extra)
    return item


def parse_feed(source: dict, payload: bytes) -> list[dict]:
    payload = payload.lstrip(b"\xef\xbb\xbf\x00\t\r\n ")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        if "junk after document element" not in str(exc) or b"</rss>" not in payload:
            raise
        root = ET.fromstring(payload[:payload.find(b"</rss>") + len(b"</rss>")])
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")]
    output: list[dict] = []
    for node in entries[:MAX_ITEMS_PER_SOURCE]:
        title = _node_text(node, ("title",))
        summary = _node_text(node, ("description", "summary", "content", "encoded"))
        link = ""
        for child in node.iter():
            if child.tag.rsplit("}", 1)[-1].lower() != "link":
                continue
            candidate = (child.attrib.get("href") or child.text or "").strip()
            relation = child.attrib.get("rel", "alternate")
            if candidate and relation in ("alternate", "self", ""):
                link = candidate
                if relation != "self":
                    break
        raw_date = _node_text(node, ("pubdate", "published", "updated", "date", "created"))
        if title and link:
            output.append(_base_item(source, title, summary, link, raw_date))
    return output


def parse_cisa(source: dict, payload: bytes) -> list[dict]:
    document = json.loads(payload.decode("utf-8", errors="replace"))
    output = []
    for record in document.get("vulnerabilities", [])[:MAX_ITEMS_PER_SOURCE]:
        cve = record.get("cveID")
        if not cve:
            continue
        date_added = record.get("dateAdded")
        output.append(_base_item(
            source,
            f"{cve} — {record.get('vendorProject', '')} {record.get('product', '')}",
            record.get("shortDescription", ""),
            f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={urllib.parse.quote(cve)}",
            f"{date_added}T00:00:00Z" if date_added else None,
            cve=cve,
        ))
    return output


def parse_usgs(source: dict, payload: bytes) -> list[dict]:
    document = json.loads(payload.decode("utf-8", errors="replace"))
    output = []
    for feature in document.get("features", [])[:MAX_ITEMS_PER_SOURCE]:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        output.append(_base_item(
            source,
            properties.get("title") or f"USGS earthquake {feature.get('id', '')}",
            f"Magnitude {properties.get('mag')}; alert {properties.get('alert') or 'none'}; significance {properties.get('sig')}; tsunami {properties.get('tsunami', 0)}.",
            properties.get("url") or source["url"],
            properties.get("time"),
            lat=coordinates[1] if len(coordinates) > 1 else None,
            lon=coordinates[0] if len(coordinates) > 1 else None,
            sensor_significance=properties.get("sig") or 0,
            tsunami=bool(properties.get("tsunami")),
        ))
    return output


FEDERAL_INTEREST = (
    "national security", "defense", "homeland security", "nuclear", "cyber", "critical infrastructure",
    "sanction", "export control", "terror", "biosecurity", "trafficking", "emergency", "foreign assets",
)


def parse_federal_register(source: dict, payload: bytes) -> list[dict]:
    document = json.loads(payload.decode("utf-8", errors="replace"))
    output = []
    for record in document.get("results", [])[:MAX_ITEMS_PER_SOURCE]:
        agencies = ", ".join(a.get("name", "") for a in record.get("agencies", []) if a.get("name"))
        title = record.get("title") or "Federal Register document"
        abstract = record.get("abstract") or ""
        if not any(term in f"{title} {agencies} {abstract}".lower() for term in FEDERAL_INTEREST):
            continue
        date = record.get("publication_date")
        output.append(_base_item(
            source, title, f"{agencies}. {abstract}",
            record.get("html_url") or record.get("raw_text_url") or source["url"],
            f"{date}T00:00:00Z" if date else None,
        ))
    return output


KNOWN_PUBLISHERS = {
    "reuters.com": ("Reuters", "wire", 0.94),
    "apnews.com": ("Associated Press", "wire", 0.94),
    "afp.com": ("Agence France-Presse", "wire", 0.93),
    "bbc.com": ("BBC", "established_media", 0.89),
    "bbc.co.uk": ("BBC", "established_media", 0.89),
    "theguardian.com": ("The Guardian", "established_media", 0.84),
    "aljazeera.com": ("Al Jazeera", "established_media", 0.82),
    "dw.com": ("Deutsche Welle", "established_media", 0.86),
}


def parse_gdelt(source: dict, payload: bytes) -> list[dict]:
    document = json.loads(payload.decode("utf-8", errors="replace"))
    output = []
    for article in document.get("articles", [])[:MAX_ITEMS_PER_SOURCE]:
        url = article.get("url") or ""
        domain = (article.get("domain") or hostname(url)).lower().removeprefix("www.")
        known = next((details for host, details in KNOWN_PUBLISHERS.items() if domain == host or domain.endswith(f".{host}")), None)
        name, source_class, reliability = known or (domain or "Unresolved publisher", "low_confidence", 0.42)
        base = dict(source)
        base.update({
            "id": f"publisher:{domain or 'unresolved'}",
            "name": name,
            "source_class": source_class,
            "reliability": reliability,
            "evidence_type": "reported_fact" if known else "discovery_pointer",
            "ownership_root": domain or "gdelt-unresolved",
        })
        item = _base_item(base, article.get("title", ""), "", url, article.get("seendate"))
        item.update({
            "discovered_via": source["id"],
            "discovery_only": not bool(known),
            "source_country": article.get("sourcecountry"),
            "language": article.get("language"),
        })
        if item["title"] and item["url"]:
            output.append(item)
    return output


PARSERS = {
    "rss": parse_feed,
    "cisa_kev": parse_cisa,
    "usgs": parse_usgs,
    "federal_register": parse_federal_register,
    "gdelt": parse_gdelt,
}


def fetch_source(source: dict) -> tuple[list[dict], str | None]:
    error = None
    options = [(source.get("url"), source.get("kind", "rss"))]
    if source.get("fallback_url"):
        options.append((source.get("fallback_url"), source.get("fallback_kind", source.get("kind", "rss"))))
    for index, (url, kind) in enumerate(options):
        if not url:
            continue
        try:
            payload = _fetch_bytes(url)
            effective_source = dict(source)
            effective_source["kind"] = kind
            if index:
                effective_source["aggregated_by"] = source.get("fallback_aggregated_by") or source.get("aggregated_by")
            parser = PARSERS[kind]
            return parser(effective_source, payload), None
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:300]
    return [], error or "no usable source URL"


def _health(source: dict, items: list[dict], error: str | None, previous: dict, now: dt.datetime) -> dict:
    old = previous.get(source["id"], {}) if isinstance(previous, dict) else {}
    if error:
        status = "failed"
    elif not items:
        status = "quiet" if source.get("sparse_ok") else "empty"
    else:
        newest = max(parse_time(item.get("published")) for item in items)
        stale_after = int(source.get("stale_after_hours", 168))
        status = "stale" if now - newest > dt.timedelta(hours=stale_after) and not source.get("sparse_ok") else "healthy"
    reachable = error is None
    useful = status in ("healthy", "quiet")
    return {
        "id": source["id"],
        "name": source["name"],
        "url": source["url"],
        "source_class": source["source_class"],
        "reliability": source.get("reliability"),
        "enabled": True,
        "status": status,
        "reachable": reachable,
        "useful": useful,
        "items": len(items),
        "error": error,
        "last_success": iso_z(now) if reachable else old.get("last_success"),
        "last_failure": iso_z(now) if error else None,
        "consecutive_failures": int(old.get("consecutive_failures", 0)) + 1 if error else 0,
        "newest_item": max((item.get("published", "") for item in items), default=None),
    }


def collect_sources(catalog: dict, previous_registry: dict | None = None, now: dt.datetime | None = None) -> tuple[list[dict], list[dict]]:
    now = now or utcnow()
    previous_by_id = {
        row.get("id"): row for row in (previous_registry or {}).get("sources", []) if row.get("id")
    }
    enabled = [source for source in catalog.get("sources", []) if source.get("enabled", True)]
    results: dict[str, tuple[list[dict], str | None]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, max(1, len(enabled)))) as executor:
        pending = {executor.submit(fetch_source, source): source for source in enabled}
        for future in concurrent.futures.as_completed(pending):
            source = pending[future]
            try:
                results[source["id"]] = future.result()
            except Exception as exc:
                results[source["id"]] = ([], f"{type(exc).__name__}: {exc}"[:300])
    items: list[dict] = []
    health: list[dict] = []
    for source in enabled:
        source_items, error = results[source["id"]]
        items.extend(source_items)
        health.append(_health(source, source_items, error, previous_by_id, now))
    for source in catalog.get("sources", []):
        if source.get("enabled", True):
            continue
        health.append({
            "id": source["id"], "name": source["name"], "url": source["url"],
            "source_class": source["source_class"], "reliability": source.get("reliability"),
            "enabled": False, "status": "disabled", "reachable": False, "useful": False,
            "items": 0, "error": source.get("disabled_reason"), "last_success": None,
            "last_failure": None, "consecutive_failures": 0, "newest_item": None,
        })
    return items, health
