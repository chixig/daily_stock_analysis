# Minute source repair

Status: active. Authorized by the user on 2026-10-05.

Objective: resolve the historical 1m/5m source conflicts and obtain independently supported full minute OHLC, retaining native intraday snapshots separately. This enables meaningful opening-window and touch-price research; this batch does not alter strategies or report returns.

Frozen previous delivery: 9a51ba137149b3e40b6160f3ed8113302a307e15.

1. Diagnose the 332 daily opening/high/low mismatches and 591 distinct conflicting minute bars.
2. Obtain direct 5m observations and repeat recent 1m observations; distinguish repeatability from independent corroboration.
3. Search and test public historical archives and documented providers. Preserve provenance and actual access outcomes; a provider claim is not downloaded evidence.
4. Replace only observations supported by sufficient evidence, preserve old values and reasons, rebuild dependent outputs, and independently verify.

No OHLC may be inferred from snapshots, interpolated, patched from daily extrema, or split from 5m. Passing daily reconciliation is insufficient to certify intraminute extrema. Unknown-provider mirrors are not independent sources. Remaining uncertainty must be explicit in the final delivery.
