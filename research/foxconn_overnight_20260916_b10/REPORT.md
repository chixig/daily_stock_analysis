# B10 Outcome-first discovery and interpretable fitting

## Good cases

| window       |   threshold |   total |   rate_pct |   model_valid_good |   n |   mean |   median |      win |        cash | pf   | pf_cash   |   worst |   tail5 |   mdd_cash |   max_loss_run |   months |   years |   clusters |       fee |   gross |   delete1 |   delete5 |   delete10 |   delete5_cash |   good_n |   good_pct |   bad_pct | recall_pct   |
|:-------------|------------:|--------:|-----------:|-------------------:|----:|-------:|---------:|---------:|------------:|:-----|:----------|--------:|--------:|-----------:|---------------:|---------:|--------:|-----------:|----------:|--------:|----------:|----------:|-----------:|---------------:|---------:|-----------:|----------:|:-------------|
| all          |      1.0000 |    2006 |    10.6181 |                188 | 213 | 2.3514 |   1.8063 | 100.0000 | 152698.4795 |      |           |  1.0012 |  1.0301 |     0.0000 |              0 |       68 |       9 |         79 | 6621.5555 |  2.5758 |    2.3163 |    2.1854 |     2.0953 |    134735.9599 |      213 |   100.0000 |    0.0000 |              |
| main2020     |      1.0000 |    1623 |    11.6451 |                188 | 189 | 2.3000 |   1.7605 | 100.0000 | 141951.5173 |      |           |  1.0012 |  1.0309 |     0.0000 |              0 |       55 |       7 |         64 | 5994.8677 |  2.5173 |    2.2601 |    2.1504 |     2.0536 |    123988.9977 |      189 |   100.0000 |    0.0000 |              |
| old2020_2023 |      1.0000 |     970 |     6.1856 |                 59 |  60 | 2.0826 |   1.4724 | 100.0000 |  20775.7326 |      |           |  1.0012 |  1.0177 |     0.0000 |              0 |       23 |       4 |         26 | 1551.3524 |  2.3500 |    1.9879 |    1.7518 |     1.5812 |     15665.8155 |       60 |   100.0000 |    0.0000 |              |
| recent2024   |      1.0000 |     653 |    19.7550 |                129 | 129 | 2.4011 |   1.8351 | 100.0000 | 121175.7848 |      |           |  1.0077 |  1.0405 |     0.0000 |              0 |       32 |       3 |         38 | 4443.5152 |  2.5951 |    2.3433 |    2.1984 |     2.0602 |    103213.2652 |      129 |   100.0000 |    0.0000 |              |
| 2020         |      1.0000 |     243 |     6.9959 |                 16 |  17 | 1.8573 |   1.5490 | 100.0000 |   4776.7962 |      |           |  1.0228 |  1.0228 |     0.0000 |              0 |        7 |       1 |          9 |  438.0088 |  2.1344 |    1.6664 |    1.3478 |     1.1805 |      2376.0904 |       17 |   100.0000 |    0.0000 |              |
| 2021         |      1.0000 |     243 |     1.2346 |                  3 |   3 | 1.5708 |   1.3818 | 100.0000 |    625.2561 |      |           |  1.0598 |  1.0598 |     0.0000 |              0 |        2 |       1 |          3 |   73.3739 |  1.8530 |    1.2208 |  nan      |   nan      |       nan      |        3 |   100.0000 |    0.0000 |              |
| 2022         |      1.0000 |     242 |     2.0661 |                  5 |   5 | 1.3792 |   1.1866 | 100.0000 |    654.1870 |      |           |  1.0012 |  1.0012 |     0.0000 |              0 |        4 |       1 |          5 |   98.7730 |  1.6940 |    1.1631 |  nan      |   nan      |       nan      |        5 |   100.0000 |    0.0000 |              |
| 2023         |      1.0000 |     242 |    14.4628 |                 35 |  35 | 2.3365 |   1.5814 | 100.0000 |  14719.4932 |      |           |  1.0292 |  1.0584 |     0.0000 |              0 |       10 |       1 |          9 |  941.1968 |  2.5910 |    2.1795 |    1.8143 |     1.5323 |      9778.1523 |       35 |   100.0000 |    0.0000 |              |
| 2024         |      1.0000 |     242 |    20.2479 |                 49 |  49 | 2.5997 |   1.9674 | 100.0000 |  28109.8782 |      |           |  1.0876 |  1.1524 |     0.0000 |              0 |       11 |       1 |         12 | 1072.9968 |  2.8026 |    2.4498 |    2.1714 |     1.9699 |     20887.3189 |       49 |   100.0000 |    0.0000 |              |
| 2025         |      1.0000 |     243 |    17.2840 |                 42 |  42 | 2.5094 |   1.8297 | 100.0000 |  45048.8806 |      |           |  1.0077 |  1.0524 |     0.0000 |              0 |       12 |       1 |         17 | 1467.8194 |  2.7032 |    2.3417 |    1.9974 |     1.7189 |     29207.3729 |       42 |   100.0000 |    0.0000 |              |
| 2026         |      1.0000 |     168 |    22.6190 |                 38 |  38 | 2.0252 |   1.7294 | 100.0000 |  48017.0259 |      |           |  1.0216 |  1.0230 |     0.0000 |              0 |        9 |       1 |          9 | 1902.6991 |  2.2081 |    1.9173 |    1.6697 |     1.4964 |     33573.6753 |       38 |   100.0000 |    0.0000 |              |

## Full-data fitted rules (IN SAMPLE)

| model            | scope              |   node | rule                                                        | training_economic_gate   |
|:-----------------|:-------------------|-------:|:------------------------------------------------------------|:-------------------------|
| case_classifier  | ALL_DATA_IN_SAMPLE |      5 | prev_vol20 > 2.56433344 AND prev_r1 <= -5.06116557          | False                    |
| return_regressor | ALL_DATA_IN_SAMPLE |      3 | prev_r20 > -16.1565018 AND tail_volume_ratio <= 0.432379827 | True                     |

## Full-data fitted results (IN SAMPLE)

| model            | window       |   n |   mean |      cash |   good_pct |   recall_pct |   bad_pct |   delete5 |
|:-----------------|:-------------|----:|-------:|----------:|-----------:|-------------:|----------:|----------:|
| case_classifier  | main2020     |  56 | 0.3704 | 5519.6991 |    39.2857 |      11.7021 |   30.3571 |   -0.0931 |
| case_classifier  | old2020_2023 |  16 | 0.0920 |   92.2161 |    31.2500 |       8.4746 |   25.0000 |   -0.9219 |
| case_classifier  | recent2024   |  40 | 0.4818 | 5427.4830 |    42.5000 |      13.1783 |   32.5000 |   -0.1571 |
| return_regressor | main2020     |  48 | 0.5403 | 8962.6989 |    29.1667 |       7.4468 |   10.4167 |    0.1192 |
| return_regressor | old2020_2023 |  29 | 0.3003 | 1542.3987 |    20.6897 |      10.1695 |   10.3448 |   -0.3985 |
| return_regressor | recent2024   |  19 | 0.9065 | 7420.3002 |    42.1053 |       6.2016 |   10.5263 |    0.0123 |

## Chronological rules

| model            |   year |   train_n | last_exit           |   chosen_node | rule                                                     | economic   |   train_good_pct |   train_net_mean |
|:-----------------|-------:|----------:|:--------------------|--------------:|:---------------------------------------------------------|:-----------|-----------------:|-----------------:|
| case_classifier  |   2022 |       465 | 2021-12-31 00:00:00 |             4 | range1450 > 4.35417008                                   | False      |         19.56522 |         -0.07074 |
| case_classifier  |   2023 |       707 | 2022-12-30 00:00:00 |             4 | range1450 > 4.35417008                                   | False      |         18.18182 |          0.00307 |
| case_classifier  |   2024 |       947 | 2023-12-29 00:00:00 |             5 | prev_vol20 > 3.18161917 AND prev_market20 <= 0.367358148 | False      |         26.38889 |         -0.13244 |
| case_classifier  |   2025 |      1189 | 2024-12-31 00:00:00 |             6 | prev_vol20 > 3.18147087 AND prev_r3 > 9.7309103          | False      |         44.00000 |          0.38978 |
| case_classifier  |   2026 |      1430 | 2025-12-31 00:00:00 |             5 | prev_vol20 > 2.56433344 AND prev_r1 <= -5.06116557       | False      |         39.13043 |          0.41729 |
| return_regressor |   2022 |       465 | 2021-12-31 00:00:00 |             2 | prev_vol20 <= 3.51903284 AND today_gap <= -0.519480914   | False      |          7.40741 |          0.00293 |
| return_regressor |   2023 |       707 | 2022-12-30 00:00:00 |             3 | today_gap <= 0.359716877 AND range1450 > 3.82157898      | False      |         18.00000 |          0.12333 |
| return_regressor |   2024 |       947 | 2023-12-29 00:00:00 |             1 | prev_r20 <= -16.1565018                                  | False      |         32.50000 |          0.37072 |
| return_regressor |   2025 |      1189 | 2024-12-31 00:00:00 |             1 | prev_r20 <= -16.1565018                                  | True       |         35.08772 |          0.39535 |
| return_regressor |   2026 |      1430 | 2025-12-31 00:00:00 |             1 | prev_r20 <= -16.1565018                                  | False      |         31.88406 |          0.37069 |

## Chronological results

| model            | year         | variant              |   n |     mean |        cash |   good_pct |   recall_pct |   bad_pct |   delete5 |
|:-----------------|:-------------|:---------------------|----:|---------:|------------:|-----------:|-------------:|----------:|----------:|
| case_classifier  | 2022         | diagnostic_best_leaf |   9 |   0.3803 |    313.4767 |    11.1111 |      20.0000 |    0.0000 |   -0.1656 |
| case_classifier  | 2022         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | 2023         | diagnostic_best_leaf | 121 |  -0.2259 |  -6401.7036 |    20.6612 |      71.4286 |   33.8843 |   -0.4714 |
| case_classifier  | 2023         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | 2024         | diagnostic_best_leaf |  61 |  -0.3181 |  -4498.4867 |    24.5902 |      30.6122 |   36.0656 |   -0.6522 |
| case_classifier  | 2024         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | 2025         | diagnostic_best_leaf |  30 |  -0.5108 |  -3460.4838 |    13.3333 |       9.5238 |   46.6667 |   -1.3275 |
| case_classifier  | 2025         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | 2026         | diagnostic_best_leaf |  10 |   0.1547 |   1409.8705 |    40.0000 |      10.5263 |   30.0000 |   -1.1469 |
| case_classifier  | 2026         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | combined2022 | diagnostic_best_leaf | 231 |  -0.2471 | -12637.3268 |    21.2121 |      28.9941 |   34.6320 |   -0.3880 |
| case_classifier  | old2022_2023 | diagnostic_best_leaf | 130 |  -0.1839 |  -6088.2269 |    20.0000 |      65.0000 |   31.5385 |   -0.4101 |
| case_classifier  | recent2024   | diagnostic_best_leaf | 101 |  -0.3285 |  -6549.1000 |    22.7723 |      17.8295 |   38.6139 |   -0.6034 |
| case_classifier  | combined2022 | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | old2022_2023 | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| case_classifier  | recent2024   | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | 2022         | diagnostic_best_leaf |  41 |  -0.2755 |  -1162.4420 |     2.4390 |      20.0000 |    7.3171 |   -0.3971 |
| return_regressor | 2022         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | 2023         | diagnostic_best_leaf |  98 |  -0.0335 |  -1257.8038 |    23.4694 |      65.7143 |   26.5306 |   -0.3027 |
| return_regressor | 2023         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | 2024         | diagnostic_best_leaf |  17 |   0.4533 |   1711.3595 |    41.1765 |      14.2857 |   29.4118 |   -0.3459 |
| return_regressor | 2024         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | 2025         | diagnostic_best_leaf |  12 |   0.2535 |  -1227.3116 |    16.6667 |       4.7619 |   33.3333 |   -1.2094 |
| return_regressor | 2025         | economic_gate        |  12 |   0.2535 |  -1227.3116 |    16.6667 |       4.7619 |   33.3333 |   -1.2094 |
| return_regressor | 2026         | diagnostic_best_leaf |   9 |   0.3806 |   1608.0359 |    44.4444 |      10.5263 |   33.3333 |   -1.6888 |
| return_regressor | 2026         | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | combined2022 | diagnostic_best_leaf | 177 |  -0.0023 |   -328.1620 |    20.9040 |      21.8935 |   23.1638 |   -0.1972 |
| return_regressor | old2022_2023 | diagnostic_best_leaf | 139 |  -0.1049 |  -2420.2458 |    17.2662 |      60.0000 |   20.8633 |   -0.2944 |
| return_regressor | recent2024   | diagnostic_best_leaf |  38 |   0.3730 |   2092.0838 |    34.2105 |      10.0775 |   31.5789 |   -0.2843 |
| return_regressor | combined2022 | economic_gate        |  12 |   0.2535 |  -1227.3116 |    16.6667 |       1.1834 |   33.3333 |   -1.2094 |
| return_regressor | old2022_2023 | economic_gate        |   0 | nan      |    nan      |   nan      |       0.0000 |  nan      |  nan      |
| return_regressor | recent2024   | economic_gate        |  12 |   0.2535 |  -1227.3116 |    16.6667 |       1.5504 |   33.3333 |   -1.2094 |

## Main factor descriptive comparisons

| window   | feature            |   good_n |   other_n |   good_median |   other_median |   bad_median |   standardized_difference |   good_vs_bad |      p |   q_descriptive |
|:---------|:-------------------|---------:|----------:|--------------:|---------------:|-------------:|--------------------------:|--------------:|-------:|----------------:|
| main2020 | prev_vol20         |      189 |      1434 |        3.6935 |         2.3570 |       3.5668 |                    0.8227 |        0.1642 | 0.0000 |          0.0000 |
| main2020 | range1450          |      189 |      1434 |        4.1853 |         2.8032 |       3.8788 |                    0.5914 |        0.0751 | 0.0000 |          0.0000 |
| main2020 | breakdown_distance |      189 |      1434 |        1.8882 |         1.0075 |       1.5113 |                    0.4258 |        0.1241 | 0.0000 |          0.0000 |
| main2020 | known_gapdays      |      189 |      1434 |        1.0000 |         1.0000 |       1.0000 |                    0.3167 |        0.2076 | 0.0051 |          0.0203 |
| main2020 | prev_relative20    |      189 |      1434 |        3.4950 |        -0.8908 |       0.6492 |                    0.3059 |       -0.0264 | 0.0030 |          0.0144 |
| main2020 | prev_bias20        |      189 |      1434 |        1.3969 |        -0.3450 |       0.6383 |                    0.2758 |        0.0397 | 0.0093 |          0.0318 |
| main2020 | prev_r20           |      189 |      1434 |        4.7072 |        -0.1866 |       2.0236 |                    0.2695 |       -0.0255 | 0.0158 |          0.0473 |
| main2020 | prev_r3            |      189 |      1434 |        0.3428 |        -0.0770 |      -0.1507 |                    0.2622 |        0.1941 | 0.0527 |          0.1151 |
| main2020 | prev_r5            |      189 |      1434 |        1.0615 |        -0.2042 |       0.0000 |                    0.2474 |        0.0977 | 0.0410 |          0.1092 |
| main2020 | morning_return     |      189 |      1434 |        0.1434 |         0.0000 |       0.0000 |                    0.2474 |        0.2510 | 0.1553 |          0.2485 |
| main2020 | prev_volume_ratio  |      189 |      1434 |        0.9775 |         0.9076 |       0.9400 |                    0.1295 |        0.0490 | 0.0759 |          0.1517 |
| main2020 | clv1450            |      189 |      1431 |        0.5147 |         0.4524 |       0.4701 |                    0.1163 |        0.1074 | 0.1387 |          0.2377 |
| main2020 | return1450         |      189 |      1434 |       -0.0546 |        -0.1070 |       0.0000 |                    0.1138 |        0.0618 | 0.4561 |          0.5761 |
| main2020 | volume_ratio1450   |      188 |      1415 |        0.9820 |         0.8963 |       0.9542 |                    0.0779 |       -0.0236 | 0.1295 |          0.2377 |
| main2020 | prev_market1       |      189 |      1434 |        0.0804 |         0.0362 |       0.0505 |                    0.0594 |        0.0619 | 0.5280 |          0.6035 |
| main2020 | prev_r1            |      189 |      1434 |       -0.0898 |        -0.0596 |       0.1375 |                    0.0014 |       -0.0947 | 0.9262 |          0.9262 |
| main2020 | afternoon_return   |      189 |      1434 |       -0.0905 |        -0.0799 |       0.0000 |                   -0.0097 |       -0.0787 | 0.8961 |          0.9262 |
| main2020 | prev_market20      |      189 |      1434 |       -0.3354 |         0.2453 |       0.0868 |                   -0.0349 |       -0.0058 | 0.3178 |          0.4386 |
| main2020 | prev_intraday      |      189 |      1434 |       -0.1481 |         0.0000 |       0.1948 |                   -0.0424 |       -0.1802 | 0.5625 |          0.6137 |
| main2020 | prev_clv           |      189 |      1431 |        0.4611 |         0.4828 |       0.5089 |                   -0.0743 |       -0.1229 | 0.3289 |          0.4386 |
| main2020 | tail_volume_ratio  |      188 |      1415 |        0.8891 |         0.8825 |       0.8978 |                   -0.0892 |       -0.1223 | 0.5107 |          0.6035 |
| main2020 | tail_return        |      189 |      1434 |       -0.0606 |         0.0000 |       0.0000 |                   -0.1047 |       -0.1961 | 0.2188 |          0.3283 |
| main2020 | today_gap          |      189 |      1434 |       -0.1223 |         0.0000 |       0.0000 |                   -0.1291 |       -0.1748 | 0.0499 |          0.1151 |
| main2020 | breakout_distance  |      189 |      1434 |       -1.7576 |        -1.3037 |      -1.9129 |                   -0.3045 |       -0.0183 | 0.0004 |          0.0024 |

## Audit

{
  "data_end": "2026-09-11",
  "main_n": 1623,
  "good_n": 189,
  "model_eligible": 1599,
  "model_good": 188,
  "missing_model_good": 1,
  "features": [
    "prev_r1",
    "prev_r3",
    "prev_r5",
    "prev_r20",
    "prev_bias20",
    "prev_vol20",
    "prev_intraday",
    "prev_clv",
    "prev_volume_ratio",
    "prev_market1",
    "prev_market20",
    "prev_relative20",
    "today_gap",
    "return1450",
    "range1450",
    "clv1450",
    "volume_ratio1450",
    "morning_return",
    "afternoon_return",
    "tail_return",
    "tail_volume_ratio",
    "breakout_distance",
    "breakdown_distance",
    "known_gapdays"
  ],
  "input_hashes": {
    "research/foxconn_overnight_20260916_b08/daily_ledger.csv": "8d5ffd55d0a21e1ca2f76c19af81f1aefd0051c67c0fc9252607b82ce1ffce1c",
    "research/foxconn_t0_20260913/results/daily_features_and_cashflows.csv": "336fd19b75d4489db11fbee4ac084744b6ea0c16802b3183bb128c43fd547e85",
    "research/foxconn_t0_20260913/source/601138-full-5min-history.zip": "6decd5fbe5916d974d7897f9259de6dbe0c319722bd3972a85d780cf25c1c5ff",
    "research/foxconn_t0_20260913_b02/source/sse_index.csv": "108cf1e67314f5c972ce064f39793368215a532ee701d6504a876a2c11d41c9c",
    "research/foxconn_t0_20260913/source/baostock_raw_crosscheck.csv": "52b880bacd8740ac79a4f7a31a8c21f2cb26e074d441797a44e9e3c8b6f97e10",
    "data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv": "78811cdfa3e493c3a65bb3d872e93fe3f66980f58673d7932c8e30e2b1d144d0"
  },
  "model_contract": "two families,depth2,minleaf40,seed601138;fullfit descriptive,annual2022-2026 causal thresholds;classifier selects highest good-rate leaf >=5 good cases,regressor highest mean;economic gate mean/delete5mean/delete5cash>0",
  "matched_cases": 189,
  "matched_unique_controls": 388,
  "checks": "parent cash/source hashes,feature mutation/prefix,training exit cutoff,prefix-identical fitted trees passed",
  "limitations": "Outcome-first full-data discovery is explicitly in-sample;historical walk-forward also uses previously viewed market history,not clean prospective OOS. Vendor dividends and execution proxy limitations inherited. No missing imputation;no new trading trigger adopted."
}