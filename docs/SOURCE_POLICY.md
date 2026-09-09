# Source and provenance policy

The catalog includes primary government/institutional sources, wire services, established media, specialist publications, regional/local reporting, OSINT analysis, expert commentary, state media, low-confidence sources, and global discovery.

Source class is a prior, not a verdict. Individual claims still need specificity, independence, corroboration, recency, and compatible evidence. Official sources are authoritative about their own statements and records, not automatically correct about every disputed underlying fact.

## Independence rules

1. The originating provenance root is the corroboration unit.
2. An outlet saying “according to Reuters/AP/AFP” inherits that wire root for the observation.
3. Multiple publications owned by the same configured root count once.
4. Anonymous-official chains receive one shared root unless evidence establishes separate origins.
5. GDELT is discovery, not evidence. A recognized publisher receives that publisher's class; unresolved domains remain discovery-only and cannot enter hard layers.
6. State-affiliated material stays visible and labeled; it can be useful as an indicator of state narrative even when factual confidence is low.

## Coverage limits

“All sources possible” is an operating aspiration, not a supportable claim. The engine cannot guarantee access to licensed wires, paywalls, private messaging, closed intelligence, robots-blocked sites, or platforms without stable public interfaces. Source failures, empty feeds, stale feeds, and disabled feeds are displayed in the system console. Optional future adapters include authenticated ReliefWeb/ACLED access and licensed commercial risk/wire services.

Adding a source requires a unique ID, class, reliability prior, evidence type, parser kind, default domain, and explicit enabled state. Tests and generated-data validation must pass before deployment.

