# B24 implementation corrections

## Revision 1 after run37029980001
First run reproduced P72 old-window entries and N0/N2 61 B11/B12 paths and completed396 accounts; report selection serialization failed because numpy int64 resource key is not a JSON object key. Preserve failed run and its branch commit b80c01160de6a0518df7c86bc89420265640182e. No independent verification had yet run.

Corrections before re-run: serialize resource keys as Python int; stock-lot end-of-day row creation no longer rewrites previous snapshots if current lots are empty; sort logical loss streaks by actual completion; recovery duration measured from prior peak; add reference price/slippage/netting/dividend/FIFO/reserve/pending exact accounting bridges; explicitly reject zero-volume completed N exit bars. All396 accounts and all downstream outputs are recalculated; no strategy thresholds or matrix changes. Synthetic tests updated to supply their completed-bar volume. Retain first-run evidence in Git history and failure archive.

Resource diagnostic audit: first run also simulated lower initial inventories to measure minimum, which was unnecessary under the task's conditional resource-grid rule. Those diagnostic accounts were not profit-ranked or added to the396 candidates. Final run starts all44F at3000, escalates only upon real inventory rejection, and obtains minimum required old shares algebraically from the old-share trough; no additional lower-resource grid. This preserves K locking before final candidate ranking.
