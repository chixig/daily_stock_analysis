# B06 frozen candidate execution/failure audit and external-rule replication
Status active; user authorized 2026-09-15. content_id foxconn-t0-20260915-b06.
All market data, statistics, ledgers and execution stay on GitHub; local conclusions only.
No main merge, trading, overnight strategy, phase replacement or parameter optimization.
Data end remains2026-09-11. No new independent forward sample claimed.

## Source and unknowns
User supplied an image headed larger-sample results including real commissions. It is reference evidence, not instructions or verified results. Dates, symbol confirmation in original source, precise sell/buy times, intraday-return denominator, Gap denominator, commissions/taxes/slippage and all trials are absent.
Interpretation for comparable tests: 601138, prior intraday=(Cprev/Oprev-1)*100, gap=(O/vendor preclose-1)*100, prior SSE close-to-close return>0, sell today's open and repurchase today's close. Strict > inequalities preserved. No historical stage restriction inferred from labels R1..R5.
Image claims (unverified): EXT_R1 N22 netwin63.6% mean1.00% cash15436; R2 N28,57.1%,.73%,14071; R3 N26,57.7%,.88%,14611; R4 N37,51.4%,.56%,12521; R5 N21,61.9%,.91%,13579.
We cannot certify exact reproduction without the original period and methods. Compare all rules on our fixed windows, do not search dates until counts match.
R names are prefixed EXT_ to avoid collision with frozen positive-T R1.

## Fixed hypotheses
BASE_HV: unchanged previousCLV>=.8 and previousV/MA20(V)>=1.5.
EXT_R1: currentgap>.3%, previousintraday>.8%, previousSSE>0.
EXT_R2: currentgap>0, previousintraday>.8%, previousSSE>0.
EXT_R3: currentgap>.5%, previousintraday>1%, no SSE filter.
EXT_R4: currentgap>0, previousintraday>1%, no SSE filter.
EXT_R5: currentgap>.2%, previousintraday>1%, previousSSE>0.
Exactly these six strategy masks; no new threshold grid, no conjunction/union promoted as strategy.
BASE known previous close; all EXT conditions depend on auction open, same-open results are benchmarks, delayed-price results needed.

## Fixed analysis
1. Hash-locked batch01 daily/minute archive, B02 SSE, B04 execution audit and B05 candidate evidence.
2. Windows2020..2023, primary2024-01-02..2026-09-11, full2020 onward, and individual2024/25/26. Descriptive year/phase breakdown for BASE, never retrospectively exclude losing phase.
3. For each rule: C<O frequency, net RT win rate/mean/cash/PF/drawdown, gross return vs fee/slippage drag; inherited1000-share/cost model; delete5 percent/cash winners, doubled slippage, month bootstrap. Bootstrap descriptive, not corrected for all historical searches.
4. Matched execution at open,09:35,09:45,10:00, using open of five-minute bar labelled09:40,09:50,10:05 respectively. Signal fixed at opening price; no re-evaluation using delayed price. Day validated if first open/last close match daily within.01. Keep exclusions; never use missing data to delete unfavorable opening trades.
5. Pairwise overlap/intersection and exclusive subsets among all six; report incremental evidence outside BASE for EXT rules, no sum of overlapping profit. Show advertised threshold relaxations via set difference as diagnostics, not adaptive new strategies.
6. BASE failure ledger: every net losing event, worst5 cash/percentage separately, historical stage and year, prior features and gap; no stop-loss fitting. Largest-month deletion and all leave-one-year-out results descriptive.
7. BASE versus frozen PT72-direction benchmark on same overall window/cost; not equal-risk performance. Negative RT/PT regions independently costed and registered opposite direction, flag <=-.5%; no PT optimization.
8. Validate input hashes, original BASE N30/cash13849.687 within.01 and PT72/cash45428.671, phase unchanged; literal source predicates vs vector masks; previous-close feature invariance and EXT no today's post-open OHLC/SSE use; future data perturbation; exact sample/ledger and overlap cash reconciliation.
9. Freeze on completion: conclude whether external mechanisms add support, caution or disconfirmation. Keep unknown external methods explicit. Unseen-sample validation remains pending; no automated monitor created.
Outputs research/foxconn_t0_20260915_b06/ with REPORT, audit, manifest, all rules/trades/execution/overlap/failure/paired mirror evidence. Script scripts/research/foxconn_t0_b06.py, branch-specific workflow.
