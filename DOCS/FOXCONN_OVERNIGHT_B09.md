# B09 pre-run contract: intraday paths and overnight continuation
Date2026-09-16; direction_id foxconn-t0; content_id foxconn-t0-20260916-b09.
User authorized continued overnight research. Primary remains CLOSE BUY -> NEXT TRADING DAY OPEN SELL. Reverse overnight candidates only registered independently,not a main-line switch. IntradayRT remains paused;frozen PT unchanged. GitHub computation only;local conclusions only;isolated branch,no main merge,monitor,live trading or external review.

## Why this batch
B08 simple daily/14:50 state conditions failed. A daily end-state does not encode the path by which it was reached. Newly constructed timestamp-causal minute-path features test afternoon recovery,late momentum and prior-range breaks. No fresh historical holdout claimed: inputs unchanged through2026-09-11 and already explored. No new external data claim.

## Eight fixed hypotheses
Use completed5min bars through14:50; no later data for signals. Opening price from09:30-09:35 bar open, morning ending11:30,tail starts14:00. Afternoon return P1450/P1130-1. Tail return P1450/P1400-1. Tail volume=sum14:05..14:50,relative to preceding20trading days of same interval;current day excluded from denominator. Reindex to daily calendar before rolling;missing bars remain unknown.
L1 tail return>0.
L2 tail return<0.
L3 morning return<0 AND afternoon return>0 (afternoon recovery).
L4 morning return>0 AND afternoon return<0 (afternoon reversal).
L5 P1450 exceeds maximum high through14:00 (breakout).
L6 P1450 below minimum low through14:00 (breakdown).
L7 tail return>0 AND tail volume ratio>=1.5.
L8 tail return<0 AND tail volume ratio>=1.5.
These path definitions are fixed before outcomes;not combinatorial searches. Flat tail days remain in baseline but neitherL1/L2. No re-optimization of0 or1.5. Only fixed14:45input-latency sensitivity;no neighboring parameter grid or added filters.

## Outcomes and comparisons
Main2020,old2020-2023,recent2024,all available and annual tables;signal-valid same-universe baseline and non-hit group,unknown counts. Primary historical fees,B08commission/minimum,1000shares,5bps each side and20% dividend-tax scenario. Parent cashflow and all input hashes must reproduce. Zero/10/20bps costs,non-dividend nights,next0935close and next0935bar-open matched delays. Primary remains auction-close purchase;cannot choose best exit afterward.
Decompose logarithmic returns P1450->C and C->nextO (tax-adjusted dividend economic component),reconcile to total. Buying at first bar open AFTER14:50 (bar ending14:55) is a diagnostic alternative and a different strategy;do not confuse contemporaneous signal price with tradable entry or automatically switch strategy. All later prices only outputs.
Mirror negative primary regions with independently costed close-sell/nextopen-rebuy relative to holding,including forgone dividend,never negate net return. Record both signs and old/recent;no reverse account certification. Account scenarios reuse finite1000 engine,not unlimited opportunity sums;limitations inherited including ex-date receivable cash treatment.

## Validation and decision
Same B08 numeric gates: mainN>=60,old/recentN>=20,positive mean in both,>=3positive years,delete5mean and cash positive,double-slippage positive,month-block95% CI and incrementalCI>0,delayed matched means>0. Holm family includes8mean+8increment tests. Execution always uncertified without queues,actual partial fills and settlement. Stage splits descriptive,not selectable extra rules. Baseline is same information-valid universe.
Annual retrospective selection2022-2026 uses completed exits beforeyear,trainingN60,>=3positive years,positive delete5mean/cash;rank delete5mean,N,ID;otherwiseNONE. No new OOS claim. Record all rules regardless of failure. If no rule passes,stop this bounded batch without adding combinations;describe whether signal advantage dissipates before close or never appears overnight.
Tests: parent cash/hash,source completeness,minute timestamps/no duplicates,future-minute mutation,prefix,dailyfinal-price irrelevance,partition counts,path log identity,training label cutoff;code/static check before push. This study has no backend or product changes,so study workflow is validation target;existing unrelated workflow failures not fixed.
