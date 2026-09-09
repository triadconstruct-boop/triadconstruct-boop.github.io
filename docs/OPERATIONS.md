# Operations

## Schedule and deployment

GitHub Actions runs at minute 7 and 37 each hour and on relevant code/config/interface changes. It compiles Python, parses the browser script, runs historical/regression tests, performs concurrent source collection, validates every generated file, and commits only `data/`. Race-safe regeneration handles a remote data update during publication.

GitHub Pages serves the main portal at `yyrv.net`. Supporting project repositories load the shared v3 interface from that domain and fetch the same public data layer.

## Reading system state

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

