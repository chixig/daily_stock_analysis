# Foxconn B04: historical swings and causal opportunity detection

Status: active. User approved execution on 2026-09-13 after reviewing the three-step plan.
content_id: foxconn-t0-20260913-b04. Data end: 2026-09-11.
Source and computation stay in GitHub; local delivery contains conclusions only.
Research branch: research/foxconn-t0-20260913-b04. No main merge or live trading.

## Fixed contract before first run
1. Reuse hash-locked batch01 daily features, original minute archive, and batch02 SSE index. No new data fetch, no new instrument.
2. All-history swing reference: close-based directional-change pivots with reversal sizes 8%, 12%, 20%. Track extrema, confirm after the specified reversal, record both extreme and confirmation dates. A completed leg excludes its start pivot and includes its end pivot. Classify U/D if at least 5 trading days and efficiency abs(log end/start)/sum(abs daily log returns)>=0.25; otherwise R. Before first and after last confirmed pivot are EDGE, not silently called R. This is scale-dependent descriptive segmentation, never a tradable label or training input.
3. Report every completed leg, day-weighted labels and fully-contained leg counts separately, overnight/intraday log decomposition, raw overnight/corporate-action reference split, gross and net RT/PT cash, and thirds of each leg. Main comparison window 2024-01-02..2026-09-11, context 2020 onward, individual years. Do not select only profitable declines.
4. Two causal detector families, four fixed variants:
   - DD2/DD3: at close enter when (prior/current trailing20 maximum close - current close)/ATR20 >=2 or3 and close<MA5. Track lowest close during active state and entry ATR. Exit on rebound >=1.5 entry ATR or two consecutive closes above MA10. Exit and entry are mutually exclusive on the same close. All OHLC for ATR are in the continuous adjusted signal scale.
   - BR10/BR20: at close enter below the prior10/20 minimum close and MA5 below its value 3 days ago; exit above the prior5 maximum close.
   - Compare unchanged frozen D baseline.
   - For each of these five masks, also report intersection with prior10-day cumulative log(C/O)<0. This produces 10 predefined RT variants, including 2 baseline variants; no other factor interactions.
   - Every mask is shifted to next trading day; no same-close information is used at that day's open. Require 80 observed days of warmup. Unknown conditions are not inferred as sideways.
5. Frozen PT U1/R1/D1/C1 and old RT UR-volume are comparators only. PT gap-dependent opening benchmark retains execution limitations.
6. Reuse fixed1000 shares and original fees/slippage, independently cost RT and PT. All mean-negative regions enter mirror registry; <=-0.5% is the inherited administrative large-loss flag. No net-return sign inversion, no optimization or promotion of PT candidates.
7. Preserve full-timeline trading for every detector. Report episodes, net cash/mean/PF/drawdown, annual results, month bootstrap95% (2000, seed601138, descriptive not selection-adjusted), delete5 winners, double slippage, matched09:35 proxy/exclusions, phase and false-activation attribution. Hindsight profitable-D coverage and first-detection lag are diagnostics only and never gate actual trades.
8. Retrospective annual walk-forward 2024/25/26: select at most one of the 8 new detector/filter variants using only 2020..previous year RT outcomes, N>=30, mean>0, cash PF>=1.3. Rank training mean descending then id; otherwise NONE. No future swing labels used for selection. This is already-inspected history, not independent unseen OOS.
9. Research follow-up hurdle for RT variants, fixed here: primary N>=30, episodes>=12, mean>=0.3%, cash PF>=1.5; each2024/25/26 N>=5 and positive mean/cash; delete5 mean/cash positive, double-slip mean/cash positive, paired delayed mean/cash positive with >=95% coverage; descriptive month95% lower bound>0. Passing only permits further validation, not trading adoption or multiplicity-adjusted statistical proof.
10. Validation: immutable parent hashes; frozen stage/PT numerical reproduction; log identity and segment coverage; synthetic cash, pivots and delayed entry checks; current/future mutation and prefix invariance of causal masks; no after-cutoff labels used by decisions; full-path cash reconciles across labels and phases. All detailed evidence and manifest committed to research branch.
11. No tuning after observing results. Defects may be corrected with recorded reason and rerun. No production pipeline changes. All study-specific documentation in English on GitHub; Chinese conclusions maintained locally, no duplicated product README/translation.

## Deliverables
research/foxconn_t0_20260913_b04/: completed segments, retrospective daily labels, causal daily masks, strategy/annual/phase and opportunity diagnostics, paired mirrors, walk-forward records, audit.json, REPORT.md, manifest.json.
scripts/research/foxconn_t0_b04.py and .github/workflows/foxconn-t0-b04.yml.
The outcome may distinguish historical opportunity existence, real-time detectability, and profitability after detection. Original four-stage formula stays frozen unless separate evidence justifies a later decision.
