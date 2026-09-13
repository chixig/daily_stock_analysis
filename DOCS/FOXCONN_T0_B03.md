# Foxconn T0 batch03
Status implemented. Bounded factor research completed; mechanical open-to-close reverse T not adopted.

## Frozen specification and source fallback
```json
{
  "content_id": "foxconn-t0-20260913-b03",
  "data_end": "2026-09-11",
  "primary": "2024-01-02 through 2026-09-11",
  "historical_audit": "2020 onward; 2023 and 2021-22 separate",
  "stage": "unchanged frozen positive V1, known at previous close; V3 not used for selection",
  "factor_count": 38,
  "tails": "causal rolling 252 available observations, min126, <=20th and >=80th percentile ranks",
  "scopes": [
    "ALL",
    "U",
    "R",
    "D",
    "C"
  ],
  "composites": 6,
  "max_rules": 410,
  "selection": "no threshold search, all results retained, no true new OOS",
  "screen": {
    "n": 30,
    "event_clusters_gap5": 12,
    "mean_net_pct": 0.3,
    "cash_pf": 1.5,
    "each_2024_2025_2026_n": 5,
    "each_year_net_mean": "positive",
    "delete_top5_net_mean_and_cash": "positive",
    "double_slippage": "positive",
    "delayed_0935_proxy": "positive",
    "month_wild_maxT_p": 0.05
  },
  "screen_meaning": "research promotion hurdle fixed before run, not proof all other strategies impossible",
  "multiplicity": "5000 calendar-month shared Rademacher wild draws, centered monthly scores; maxT across all eligible rules; within-batch only",
  "walk_forward": "for each 2024/25/26 train only 2020..prior year, n>=30 and PF>=1.3; choose highest mean, tie id; top1 only, no retuning",
  "price_models": "O-C benchmark and 09:35 approximate next-bar open; after-open factors cannot trade at auction O",
  "US": "latest NY16:00 close before Shanghai09:25, max7 days stale; FRED or identical Yahoo index fallback, current vintage; historical publication timestamps unverified",
  "PT": "frozen U1/R1/D1/C1 direction layer only; fixed1000 shares for comparison, not original position schedule or discretionary confirmation",
  "attribution": "log(C/preclose)=log(O/preclose)+log(C/O); raw prior actual close and corporate-action adjustment separately",
  "mirror": "all negative cells paired with independently costed opposite direction; large flag <=-0.5pct",
  "stop": "if no qualifying literal-open RT rule, conclude not adopted in this defined scope, not universal mathematical impossibility"
}
```

## Verified outcome and decision

Final run 34748296586 succeeded. Code 2ba44af48d1a77e8ef969baf99ca7847cfe4bd1d; result 9c13b3e507e00b05222f8e332ebc38cae301f17b. All 38 factors obtained; FRED timed out, identical Nasdaq/SOX indices obtained from Yahoo with NY/Shanghai alignment. Current vendor vintage, not historical publication-vintage certification.
410 registered cells, 392 nonempty, 239 with N>=30. Twenty N>=30 cells had positive means; none survived deletion of the best five returns and none was positive in all three calendar years. No rule passed the basic hurdle. 322 negative-mean cells, 229 at or below -0.5%, preserve independently costed mirrors with overlap and scope labels.
Frozen PT direction matrix, primary N72: mean 1.616%, cash 45428.671, cash PF4.342. Original PT 91-trade ledger not claimed identical. Matched N71: opening cash 45399.025 versus delayed proxy 30399.983; D1 delayed negative. Old RT volume N23 and R deceleration N15 remain historical evidence, not execution rules.
For 166 causal D days, mean overnight log return -0.25756% and intraday +0.25657%; near cancellation. D describes prior weakness, not guaranteed next-day decline. Hindsight actual peak-trough intervals include both overnight and intraday declines, often before D classification. Corporate-action reference changes separately recorded. Hindsight peak/trough labels never used as entry factors.
Decision under the user's stopping condition: do not adopt mechanical open-sell/close-buy RT; close repeated historical factor tuning in this scope. This does not establish that all intraday or overnight RT mechanisms are impossible. PT remains an execution-unvalidated research baseline. No overnight strategy, prospective automation or live trading started.
Validation: parent hashes, frozen-stage consistency, deterministic cash flows, three historical feature-mutation cutoffs, exact log decomposition, and matched execution dates. Common cash scenario is an ex-post feasibility audit; insufficient funds are reported, never used to delete trades based on future closing needs. Main branch unchanged. All data/computation/evidence stay GitHub; local conclusion and project-context updates only.
