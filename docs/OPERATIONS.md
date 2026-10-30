# Operations

## Schedule and deployment

GitHub Actions runs at minute 7 and 37 each hour and on relevant code/config/interface changes. It compiles Python, parses the browser script, runs historical/regression tests, performs concurrent source collection, validates every generated file, and commits only `data/`. Race-safe regeneration handles a remote data update during publication.

GitHub Pages serves the main portal at `yyrv.net`. Supporting project repositories load the shared v3 interface from that domain and fetch the same public data layer.

## Reading system state

WORLDWATCH opens on a 24-report worldwide overview that rotates through geographic desks and topics. The Region and Conflict / Topic dropdowns drill into the same evidence states; regional views retain the existing priority order and offer additional reports through “Show more reports.” Headline geography sets the main browsing desk; ambiguous multi-region briefings remain global. Desk labels describe a story's subject geography, not a verified incident location.

The WORLDWATCH export reserves regional and conflict/topic coverage before its 250-record limit, so a busy conflict cannot consume every slot before other regions reach the interface. The worldwide overview assigns each report to one main desk to avoid counting a multi-region story several times. Confidence, threat, watch priority, source collection, and the other tools' selection rules remain unchanged. A zero count indicates no matching exported reports, not that a region is quiet. Earlier curated briefings are preserved in a closed archive below the live view.

| Status | Interpretation |
|---|---|
| Active with coverage | Active claims and at least 90% useful configured coverage |
| Active with gaps | Active claims exist, but one or more material feeds/classes are impaired |
| Quiet with coverage | Few/no active claims with adequate collection coverage |
| Quiet with discovery gap | Few/no active claims and inadequate coverage; silence is not meaningful |
| Collection gap | Coverage is below the minimum dependable operating level |

`healthy` means reachable with current items; `quiet` is a reachable sparse sensor with no item; `empty` is an unexpectedly empty normal feed; `stale` has items but no recent publication; `failed` is a connection or parse failure.

## Incident checklist

1. Check the latest Y&Y Intelligence Engine workflow and the Pages deployment.
2. Open `/system/` and inspect coverage, class-level health, last success, blind spots, and last poll age.
3. Re-run the workflow once for transient failures; do not hide persistent gaps.
4. For rule changes, run offline reanalysis plus all tests and validators.
5. Never manually relabel a claim by editing generated JSON. Change evidence/rules, add a reviewed override mechanism, or record an explicit source correction.


