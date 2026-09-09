# Confidence, threat, and watch scoring

## Confidence

Confidence is a bounded analytical score, not a probability. It is recomputed on every run:

| Component | Weight | Purpose |
|---|---:|---|
| Source quality | 23% | Reliability of the best supporting sources |
| Independence | 16% | Unique originating provenance roots |
| Corroboration | 14% | Independent roots plus limited same-root detail |
| Specificity | 12% | Concrete actors, places, times, numbers, and falsifiable action |
| Recency | 12% | Decay from the newest material evidence time |
| Evidence type | 10% | Sensor/legal/official data vs. reporting/analysis/user claims |
| Historical reliability | 8% | Reliability history encoded in source policy |
| Claim maturity | 5% | Evidence accumulation and time for assessment |
| Contradiction | −35% | Credible independent refuting evidence |

Discovery pointers do not contribute to hard corroboration. State-affiliated reporting is visibly labeled and receives its configured reliability prior. A single wire report can become `CREDIBLE REPORT`, but not `CONFIRMED`; two rewrites attributing Reuters still count as one root.

## State gates

- `CONFIRMED`: direct primary sensor/legal/official data at adequate confidence, or at least two independent credible roots at the confirmation threshold, without unresolved speculative framing.
- `CREDIBLE REPORT`: credible sourcing clears the report threshold but confirmation is incomplete.
- `EARLY WARNING`: warning, buildup, preparation, mobilization, alert, or escalation cues before hard confirmation.
- `SPECULATIVE`: explicitly conditional, possible, alleged, or rumor-framed reporting.
- `UNVERIFIED CLAIM`: insufficient credible evidence or unresolved discovery.
- `REFUTED`: credible contrary evidence outweighs or stands without credible support. Its threat and watch contributions are zero.
- `DORMANT`: no new material evidence for 14 days. The record remains preserved.

## Threat versus watch

Impact severity estimates consequence if the report is true. Threat score heavily discounts weak states by confidence. Watch priority deliberately grants early-warning and speculative cues an additional boost, then adds bounded cross-domain, anomaly, and historical-pattern cues. This is the false-negative safeguard: investigate early without presenting the item as fact.

WWT and THRESHOLD cap contributions by provenance root so syndication cannot create runaway pressure. Verified and weak-signal channels are calculated and displayed separately.

