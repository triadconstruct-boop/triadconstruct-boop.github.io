# Y&Y Intelligence Engine

Y&Y is a public-source, layered early-warning system. Version 3 preserves the original hard-evidence stream and adds explicit handling for credible reports, weak signals, speculation, unverified claims, refutations, and dormant history.

> **Collect broadly. Classify aggressively. Believe cautiously. Preserve everything useful.**

The system never equates collection with truth. Every visible claim is labeled as one of:

- `CONFIRMED`
- `CREDIBLE REPORT`
- `EARLY WARNING`
- `SPECULATIVE`
- `UNVERIFIED CLAIM`
- `REFUTED`
- `DORMANT`

## What changed in v3

- Sixty enabled public feeds across official, wire, established-media, specialist, regional/local, OSINT, expert, state-media, low-confidence, and discovery classes.
- Stable observations are clustered into lifecycle claims instead of scored as unrelated articles.
- Syndicated coverage is traced to a provenance root, so ten rewrites of one wire report count as one source.
- Supporting and contradictory observations remain attached to the claim.
- Confidence can rise, fall, or decay and is separate from impact severity.
- Weak signals can raise watch priority without materially inflating hard threat scores.
- Refuted and dormant records remain available for pattern analysis.
- Cross-domain convergence, anomaly cues, retained historical memory, and branch/falsifier generation are included.
- WORLDWATCH accepts immediate speculative reporting but labels it at every presentation point.
- THRESHOLD separates `Confirmed Homeland Signal` from `Precursor / Speculative Signal`.
- WWT separates `Verified Pressure` from `Early-Warning Pressure`.
- A dedicated [system console](https://yyrv.net/system/) distinguishes quiet-with-coverage from collection failure.

## Run locally

```bash
python3 scripts/y_and_y_autonomous.py           # collect and analyze
python3 scripts/y_and_y_autonomous.py --offline # re-score preserved evidence only
python3 -m unittest discover -s tests -v
python3 scripts/validate_generated.py
python3 scripts/validate_site.py
node --check assets/y-and-y-live.js
```

The scheduled GitHub workflow runs every 30 minutes, validates the engine and interface, executes the regression suite, collects sources, validates every generated product, and commits only `data/`.

## Repository map

| Path | Purpose |
|---|---|
| `config/source-catalog.json` | Source classes, reliability priors, evidence types, endpoints, and enabled state |
| `scripts/yy_engine/ingest.py` | Concurrent collection, parsing, publisher resolution, and source health |
| `scripts/yy_engine/rules.py` | Domain, actor, geography, stance, and impact rules |
| `scripts/yy_engine/analysis.py` | Clustering, lifecycle, confidence, scores, anomalies, branches, and memory |
| `scripts/yy_engine/pipeline.py` | Persistent state and public products |
| `tests/` | Historical replay and regression cases |
| `data/` | Machine-generated observations, claims, audits, diagnostics, and interfaces |
| `assets/y-and-y-live.js` | Shared red/black terminal intelligence layer |
| `system/` | Source, ingestion, state, confidence, anomaly, and blind-spot console |
| `docs/` | Architecture, scoring, source policy, operations, and audit record |

## Boundaries

Y&Y uses public sources and deterministic rules. It is not an intelligence service, emergency authority, calibrated probability model, or substitute for expert review. No public-source system can literally ingest every source: private channels, paywalled/licensed feeds, access-controlled platforms, deleted material, and collection outages remain blind spots. Version 3 makes those gaps visible instead of treating absent data as evidence that nothing is happening.
