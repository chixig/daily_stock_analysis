# B16 implementation notes

Source inspection first pass incorrectly treated existing UTF-8 .txt extraction as legacy HTML; this was identified before account computation and fixed by re-extracting the two existing verified PDFs, without re-fetching them. Initial cninfo query returned no rows because security orgId was missing. Official stock lookup resolved orgId, allowing all seven missing primary PDFs to be retrieved once. Failed SSE snapshots and earlier catalogue/reprint attempts remain recorded, not accepted as PDFs.

The main computation's live tee log gained its final completion line after the initial manifest was calculated. Final verification permits only that expected live-log difference, preserves the original manifest as calculation_manifest.json, and hashes the closed log. All account/result/source inputs and old627 files must remain unchanged. No signal, capital, cost grid or numerical-result correction made.

Known2026-05-15 price discrepancy remains unresolved; no corrected-price simulation. Fixed budget is explanatory only; extra11/12bp paths independently reconstructed and first shortfall cases inspected.
