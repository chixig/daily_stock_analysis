# Hindsight decline intervals: literal open-sell close-buy audit

{
  "intervals": 8,
  "positive_net_cash_intervals": 4,
  "positive_net_mean_intervals": 4,
  "cash_and_mean_both_positive": 4,
  "every_interval_contains_net_profitable_days": true,
  "boundary": "Existence of hindsight profitable intervals is separate from their causal detectability. Stock decline alone does not imply daily open-close RT net profit."
}

| peak       | trough     |   n |   stock_decline_pct |   linked_intraday_pct |   gross_RT_mean_pct |   net_RT_mean_pct |   gross_RT_cash |   net_RT_cash |   cost_and_slippage_cash |   win_pct |   profitable_days |   losing_days |   D_days |   nonD_days |   D_net_RT_cash |   nonD_net_RT_cash |   oracle_only_winners_cash |
|:-----------|:-----------|----:|--------------------:|----------------------:|--------------------:|------------------:|----------------:|--------------:|-------------------------:|----------:|------------------:|--------------:|---------:|------------:|----------------:|-------------------:|---------------------------:|
| 2020-01-22 | 2022-10-10 | 654 |             -57.312 |               -33.162 |               0.047 |            -0.237 |        4580.000 |    -18661.938 |                23241.938 |    42.508 |               278 |           376 |      206 |         448 |       -5601.239 |         -13060.699 |                  44692.627 |
| 2023-07-14 | 2024-01-17 | 126 |             -52.329 |               -30.522 |               0.254 |             0.032 |        7080.000 |      2071.631 |                 5008.369 |    55.556 |                70 |            56 |       68 |          58 |       -2726.856 |           4798.487 |                  23983.159 |
| 2024-07-09 | 2025-04-08 | 180 |             -45.274 |               -11.227 |               0.033 |            -0.164 |        3200.000 |     -4670.225 |                 7870.225 |    50.556 |                91 |            89 |       72 |         108 |       -3955.525 |           -714.700 |                  36501.308 |
| 2025-10-29 | 2026-03-23 |  95 |             -40.768 |                -6.166 |               0.029 |            -0.150 |        3860.000 |     -6437.110 |                10297.110 |    46.316 |                44 |            51 |       44 |          51 |       -2494.313 |          -3942.797 |                  59717.047 |
| 2026-06-03 | 2026-07-30 |  40 |             -33.621 |               -19.639 |               0.475 |             0.296 |       13910.000 |      9063.723 |                 4846.277 |    52.500 |                21 |            19 |       10 |          30 |        4387.174 |           4676.549 |                  46650.948 |
| 2023-04-18 | 2023-05-12 |  15 |             -25.169 |               -21.304 |               1.468 |             1.206 |        4120.000 |      3471.609 |                  648.391 |    60.000 |                 9 |             6 |        0 |          15 |           0.000 |           3471.609 |                   6127.472 |
| 2025-09-23 | 2025-10-14 |   9 |             -15.733 |                -7.056 |               0.745 |             0.566 |        4680.000 |      3613.543 |                 1066.457 |    55.556 |                 5 |             4 |        0 |           9 |           0.000 |           3613.543 |                  10214.547 |
| 2023-06-19 | 2023-07-12 |  15 |             -14.853 |                -3.107 |               0.151 |            -0.092 |         800.000 |       -77.278 |                  877.278 |    53.333 |                 8 |             7 |        0 |          15 |           0.000 |            -77.278 |                   5020.391 |

These intervals were selected by realized drawdowns in batch03, not by a new return search. Fixed 1000 old shares, same price/cost scenario. Net cash is incremental T cash, not portfolio return. Oracle selection only describes ex-post opportunities. No live strategy, new stage formula or overnight strategy is introduced.
