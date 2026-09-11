#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ["index.html", "worldwatch/index.html", "atlas/index.html", "infrawatch/index.html", "brief/index.html", "threshold/index.html", "wwt/index.html", "trfk/index.html", "edges/index.html", "intake/index.html", "academy/index.html", "nexus/index.html", "system/index.html"]


def main() -> int:
    for relative in ROUTES:
        path = ROOT / relative
        if not path.exists():
            raise SystemExit(f"missing terminal route: {relative}")
        text = path.read_text(encoding="utf-8")
        if "y-and-y-live.js" not in text:
            raise SystemExit(f"shared intelligence interface missing from {relative}")
    root = (ROOT / "index.html").read_text(encoding="utf-8")
    if 'value="/system/"' not in root:
        raise SystemExit("SYSTEM STATUS is missing from the selector")
    system = (ROOT / "system" / "index.html").read_text(encoding="utf-8")
    required = ("SOURCE HEALTH", "CLAIM STATES", "CONFIDENCE DISTRIBUTION", "COLLECTION BLIND SPOTS", "ANOMALIES")
    if any(label not in system for label in required):
        raise SystemExit("system diagnostics view is incomplete")
    asset = (ROOT / "assets" / "y-and-y-live.js").read_text(encoding="utf-8")
    labels = ("CREDIBLE REPORT", "EARLY WARNING", "SPECULATIVE", "UNVERIFIED CLAIM", "REFUTED", "DORMANT", "VERIFIED PRESSURE", "CONFIRMED HOMELAND SIGNAL")
    if any(label not in asset for label in labels):
        raise SystemExit("shared UI does not expose every required state/signal label")
    if 'option.value = "/edges/"' not in asset or "registerPortalRoute" not in asset:
        raise SystemExit("EDGES is missing from the portal selector registration")
    edges = (ROOT / "edges" / "index.html").read_text(encoding="utf-8")
    if any(label not in edges for label in ("REMOVE NAMES. LEAVE EDGES.", "DIRECT", "REPORTED", "ANALYTICAL", "HISTORICAL", "NON-INFERENCE RULE")):
        raise SystemExit("EDGES evidence boundaries are incomplete")
    if not (ROOT / "assets" / "edges.js").exists():
        raise SystemExit("EDGES interaction layer is missing")
    if (ROOT / "CNAME").read_text(encoding="utf-8").strip() != "yyrv.net":
        raise SystemExit("unexpected Pages domain")
    print(f"Y&Y site validation passed: {len(ROUTES)} terminal routes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
