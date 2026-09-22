# R1 final verification and attribution

All arithmetic remains remote. No new scenarios or parameters.

## Final order verification

| scenario                    |   orders | status   | checks                                                                                                              |
|:----------------------------|---------:|:---------|:--------------------------------------------------------------------------------------------------------------------|
| S0_0_paid_open_5            |       86 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_0_locked_open_5          |       29 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_10_paid_open_5           |      216 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_10_locked_open_5         |      159 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_paid_open_5           |      445 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_locked_open_5         |      403 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_0_paid_open_5         |       91 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_0_locked_open_5       |       49 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_10_paid_open_5        |      311 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_10_locked_open_5      |      251 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_paid_open_5        |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_locked_open_5      |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_0_paid_open_5         |       93 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_0_locked_open_5       |       32 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_10_paid_open_5        |      211 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_10_locked_open_5      |      154 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_30_paid_open_5        |      675 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S2_F2_30_locked_open_5      |      645 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_paid_open_10       |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_paid_post0935_5    |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_paid_post0935_10   |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_locked_open_10     |      339 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_locked_post0935_5  |      572 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S1_F1_30_locked_post0935_10 |      299 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_paid_open_10          |      268 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_paid_post0935_5       |      664 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_paid_post0935_10      |      400 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_locked_open_10        |      238 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_locked_post0935_5     |      495 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |
| S0_30_locked_post0935_10    |      330 | PASS     | independent window timing, source price, per-leg slippage and historical fee, event inventory, financial invariants |

## A selected original dependencies

| account             |   intraday_buy_orders |   intraday_quantity |   intraday_fees |   suppressed_window_exposure_days | first_intraday   | classification                     |
|:--------------------|----------------------:|--------------------:|----------------:|----------------------------------:|:-----------------|:-----------------------------------|
| S0_0_locked         |                    10 |                1000 |       50.228744 |                               526 | 2020-03-04       | retrospective_QC_dependency        |
| S0_0_restricted     |                    13 |                1300 |       65.302931 |                               525 | 2020-03-04       | retrospective_QC_dependency        |
| S0_10_locked        |                    11 |                1100 |       55.255858 |                               526 | 2020-07-16       | retrospective_QC_dependency        |
| S0_10_restricted    |                    12 |                1200 |       60.272236 |                               525 | 2020-07-16       | retrospective_QC_dependency        |
| S0_30_locked        |                     8 |                 800 |       40.170715 |                               526 | 2021-07-02       | retrospective_QC_dependency        |
| S0_30_restricted    |                     7 |                 700 |       35.162481 |                               520 | 2021-07-02       | retrospective_QC_dependency        |
| S1_F1_0_locked      |                    10 |                1000 |       50.231366 |                               526 | 2020-03-04       | retrospective_QC_dependency        |
| S1_F1_0_restricted  |                    12 |                1200 |       60.303352 |                               513 | 2020-03-04       | retrospective_QC_dependency        |
| S1_F1_10_locked     |                     1 |                 100 |        5.008864 |                               526 | 2022-09-19       | retrospective_QC_dependency        |
| S1_F1_10_restricted |                     1 |                 100 |        5.010885 |                               497 | 2023-03-07       | retrospective_QC_dependency        |
| S1_F1_30_locked     |                     0 |                   0 |        0.000000 |                                 0 | nan              | no_intraday_or_suppressed_exposure |
| S1_F1_30_restricted |                     0 |                   0 |        0.000000 |                                 0 | nan              | no_intraday_or_suppressed_exposure |
| S2_F2_0_locked      |                     3 |                 300 |       15.076458 |                               526 | 2020-03-16       | retrospective_QC_dependency        |
| S2_F2_0_restricted  |                     8 |                 800 |       40.187374 |                               519 | 2020-03-16       | retrospective_QC_dependency        |
| S2_F2_10_locked     |                     7 |                 700 |       35.137679 |                               526 | 2021-05-24       | retrospective_QC_dependency        |
| S2_F2_10_restricted |                     6 |                 600 |       30.128024 |                               519 | 2021-07-02       | retrospective_QC_dependency        |
| S2_F2_30_locked     |                     1 |                 100 |        5.023122 |                               519 | 2023-06-27       | retrospective_QC_dependency        |
| S2_F2_30_restricted |                     0 |                   0 |        0.000000 |                                 5 | nan              | retrospective_QC_dependency        |

## C paid versus locked trading divergence

| rule   | first_window   |   slip_bp | first_order_record_difference   | first_quantity_or_participation_difference   |   changed_physical_orders |
|:-------|:---------------|----------:|:--------------------------------|:---------------------------------------------|--------------------------:|
| S1_F1  | open           |         5 | 2021-08-02 00:00:00             | NaT                                          |                         0 |
| S1_F1  | open           |        10 | 2021-08-02 00:00:00             | 2023-08-24 00:00:00                          |                       243 |
| S1_F1  | post0935       |         5 | 2021-08-02 00:00:00             | NaT                                          |                         0 |
| S1_F1  | post0935       |        10 | 2021-08-02 00:00:00             | 2023-03-24 00:00:00                          |                       277 |
| S0     | open           |         5 | 2021-07-28 00:00:00             | 2021-07-28 00:00:00                          |                        88 |
| S0     | open           |        10 | 2021-07-28 00:00:00             | 2021-07-28 00:00:00                          |                        72 |
| S0     | post0935       |         5 | 2021-07-27 00:00:00             | 2021-12-16 00:00:00                          |                       195 |
| S0     | post0935       |        10 | 2021-07-28 00:00:00             | 2021-07-28 00:00:00                          |                        92 |

## C payment first divergence cases

| scenario                    | date                |         cash |   receivable |   shares |   buy_quantity |   sell_quantity |   restoration_missing_shares |   relative_equity |
|:----------------------------|:--------------------|-------------:|-------------:|---------:|---------------:|----------------:|-----------------------------:|------------------:|
| S1_F1_30_paid_open_10       | 2023-08-23 00:00:00 | 23762.998575 |     0.000000 |        0 |              0 |            1000 |                            0 |      -4591.001425 |
| S1_F1_30_paid_open_10       | 2023-08-24 00:00:00 |  1235.273350 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5778.726650 |
| S1_F1_30_paid_open_10       | 2023-08-25 00:00:00 |  1235.273350 |     0.000000 |     1000 |              0 |               0 |                            0 |      -5778.726650 |
| S1_F1_30_paid_open_10       | 2023-08-28 00:00:00 |  1235.273350 |     0.000000 |     1000 |              0 |               0 |                            0 |      -5778.726650 |
| S1_F1_30_locked_open_10     | 2023-08-23 00:00:00 | 22462.998575 |  1300.000000 |        0 |              0 |            1000 |                            0 |      -4591.001425 |
| S1_F1_30_locked_open_10     | 2023-08-24 00:00:00 |  2187.545873 |  1300.000000 |      900 |            900 |               0 |                          100 |      -5769.454127 |
| S1_F1_30_locked_open_10     | 2023-08-25 00:00:00 |    60.404651 |  1300.000000 |     1000 |            100 |               0 |                            0 |      -5653.595349 |
| S1_F1_30_locked_open_10     | 2023-08-28 00:00:00 |    60.404651 |  1300.000000 |     1000 |              0 |               0 |                            0 |      -5653.595349 |
| S1_F1_30_paid_post0935_10   | 2023-03-23 00:00:00 | 17788.103283 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5665.896717 |
| S1_F1_30_paid_post0935_10   | 2023-03-24 00:00:00 |   635.801812 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5828.198188 |
| S1_F1_30_paid_post0935_10   | 2023-03-27 00:00:00 | 18225.383318 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5868.616682 |
| S1_F1_30_paid_post0935_10   | 2023-03-28 00:00:00 |  1233.243448 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5230.756552 |
| S1_F1_30_locked_post0935_10 | 2023-03-23 00:00:00 | 17038.103283 |   750.000000 |        0 |              0 |            1000 |                            0 |      -5665.896717 |
| S1_F1_30_locked_post0935_10 | 2023-03-24 00:00:00 |  1600.531959 |   750.000000 |      900 |            900 |               0 |                          100 |      -5879.468041 |
| S1_F1_30_locked_post0935_10 | 2023-03-27 00:00:00 |  1600.531959 |   750.000000 |      900 |              0 |               0 |                          100 |      -5876.468041 |
| S1_F1_30_locked_post0935_10 | 2023-03-28 00:00:00 |  1600.531959 |   750.000000 |      900 |              0 |               0 |                          100 |      -5758.468041 |
| S0_30_paid_open_5           | 2021-07-27 00:00:00 |  1382.393314 |     0.000000 |      900 |              0 |               0 |                          100 |      -5754.606686 |
| S0_30_paid_open_5           | 2021-07-28 00:00:00 |   248.806743 |     0.000000 |     1000 |            100 |               0 |                            0 |      -5760.193257 |
| S0_30_paid_open_5           | 2021-07-29 00:00:00 | 11172.107547 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5781.892453 |
| S0_30_paid_open_5           | 2021-07-30 00:00:00 |   201.408238 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5762.591762 |
| S0_30_locked_open_5         | 2021-07-27 00:00:00 |  1157.393314 |   225.000000 |      900 |              0 |               0 |                          100 |      -5754.606686 |
| S0_30_locked_open_5         | 2021-07-28 00:00:00 |  1157.393314 |   225.000000 |      900 |              0 |               0 |                          100 |      -5726.606686 |
| S0_30_locked_open_5         | 2021-07-29 00:00:00 |    46.818703 |   225.000000 |     1000 |            100 |               0 |                            0 |      -5737.181297 |
| S0_30_locked_open_5         | 2021-07-30 00:00:00 | 11199.770025 |   225.000000 |        0 |              0 |            1000 |                            0 |      -5759.229975 |
| S0_30_paid_open_10          | 2021-07-27 00:00:00 |  1383.936649 |     0.000000 |      900 |              0 |               0 |                          100 |      -5753.063351 |
| S0_30_paid_open_10          | 2021-07-28 00:00:00 |   249.786066 |     0.000000 |     1000 |            100 |               0 |                            0 |      -5759.213934 |
| S0_30_paid_open_10          | 2021-07-29 00:00:00 | 11167.597476 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5786.402524 |
| S0_30_paid_open_10          | 2021-07-30 00:00:00 |   191.418057 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5772.581943 |
| S0_30_locked_open_10        | 2021-07-27 00:00:00 |  1158.936649 |   225.000000 |      900 |              0 |               0 |                          100 |      -5753.063351 |
| S0_30_locked_open_10        | 2021-07-28 00:00:00 |  1158.936649 |   225.000000 |      900 |              0 |               0 |                          100 |      -5725.063351 |
| S0_30_locked_open_10        | 2021-07-29 00:00:00 |    47.809527 |   225.000000 |     1000 |            100 |               0 |                            0 |      -5736.190473 |
| S0_30_locked_open_10        | 2021-07-30 00:00:00 | 11195.156571 |   225.000000 |        0 |              0 |            1000 |                            0 |      -5763.843429 |
| S0_30_paid_post0935_5       | 2021-12-15 00:00:00 | 12140.351505 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5693.648495 |
| S0_30_paid_post0935_5       | 2021-12-16 00:00:00 |   199.147786 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5764.852214 |
| S0_30_paid_post0935_5       | 2021-12-17 00:00:00 | 12315.701177 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5788.298823 |
| S0_30_paid_post0935_5       | 2021-12-20 00:00:00 |   114.362255 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5849.637745 |
| S0_30_locked_post0935_5     | 2021-12-15 00:00:00 | 11890.351505 |   250.000000 |        0 |              0 |            1000 |                            0 |      -5693.648495 |
| S0_30_locked_post0935_5     | 2021-12-16 00:00:00 |  1142.768157 |   250.000000 |      900 |            900 |               0 |                          100 |      -5776.231843 |
| S0_30_locked_post0935_5     | 2021-12-17 00:00:00 |  1142.768157 |   250.000000 |      900 |              0 |               0 |                          100 |      -5785.231843 |
| S0_30_locked_post0935_5     | 2021-12-20 00:00:00 |  1142.768157 |   250.000000 |      900 |              0 |               0 |                          100 |      -5781.231843 |
| S0_30_paid_post0935_10      | 2021-07-27 00:00:00 |  1329.648835 |     0.000000 |      900 |              0 |               0 |                          100 |      -5784.851165 |
| S0_30_paid_post0935_10      | 2021-07-28 00:00:00 |   195.498252 |     0.000000 |     1000 |            100 |               0 |                            0 |      -5791.001748 |
| S0_30_paid_post0935_10      | 2021-07-29 00:00:00 | 11135.809662 |     0.000000 |        0 |              0 |            1000 |                            0 |      -5818.190338 |
| S0_30_paid_post0935_10      | 2021-07-30 00:00:00 |   289.762845 |     0.000000 |     1000 |           1000 |               0 |                            0 |      -5674.237155 |
| S0_30_locked_post0935_10    | 2021-07-27 00:00:00 |  1104.648835 |   225.000000 |      900 |              0 |               0 |                          100 |      -5784.851165 |
| S0_30_locked_post0935_10    | 2021-07-28 00:00:00 |  1104.648835 |   225.000000 |      900 |              0 |               0 |                          100 |      -5756.851165 |
| S0_30_locked_post0935_10    | 2021-07-29 00:00:00 |  1104.648835 |   225.000000 |      900 |              0 |               0 |                          100 |      -5755.851165 |
| S0_30_locked_post0935_10    | 2021-07-30 00:00:00 |  1104.648835 |   225.000000 |      900 |              0 |               0 |                          100 |      -5778.851165 |

## A first repair divergence S0_0_paid_open_5

| scenario         | date                | clock   | side   |   quantity_old |   reference_old |    value_old |   fee_old |   dividend_tax_old |   cash_after_old |   shares_after_old |   sequence |   quantity_new |   reference_new |    value_new |    fee_new |   dividend_tax_new |   cash_after_new |   shares_after_new | _merge    |
|:-----------------|:--------------------|:--------|:-------|---------------:|----------------:|-------------:|----------:|-------------------:|-----------------:|-------------------:|-----------:|---------------:|----------------:|-------------:|-----------:|-------------------:|-----------------:|-------------------:|:----------|
| S0_0_paid_open_5 | 2020-03-04 00:00:00 | 13:05   | BUY    |     100.000000 |       16.850000 |  1685.842500 |  5.033717 |           0.000000 |         1.542071 |        1000.000000 |          0 |     nan        |      nan        |   nan        | nan        |         nan        |       nan        |         nan        | left_only |
| S0_0_paid_open_5 | 2020-03-05 00:00:00 | 15:00   | SELL   |    1000.000000 |       17.160000 | 17151.420000 | 22.494448 |           0.000000 |     17130.467622 |           0.000000 |          0 |     nan        |      nan        |   nan        | nan        |         nan        |       nan        |         nan        | left_only |
| S0_0_paid_open_5 | 2020-03-06 00:00:00 | 09:25   | BUY    |    1000.000000 |       16.830000 | 16838.415000 |  5.336768 |           0.000000 |       286.715854 |        1000.000000 |          0 |     100.000000 |       16.830000 |  1683.841500 |   5.033677 |           0.000000 |         3.543111 |        1000.000000 | both      |
| S0_0_paid_open_5 | 2020-03-09 00:00:00 | 15:00   | SELL   |    1000.000000 |       16.180000 | 16171.910000 | 21.495348 |           0.000000 |     16437.130506 |           0.000000 |          0 |    1000.000000 |       16.180000 | 16171.910000 |  21.495348 |           0.000000 |     16153.957762 |           0.000000 | both      |

## A first repair divergence S2_F2_30_locked_open_5

| scenario               | date                | clock   | side   |   quantity_old |   reference_old |   value_old |    fee_old |   dividend_tax_old |   cash_after_old |   shares_after_old |   sequence |   quantity_new |   reference_new |   value_new |    fee_new |   dividend_tax_new |   cash_after_new |   shares_after_new | _merge     |
|:-----------------------|:--------------------|:--------|:-------|---------------:|----------------:|------------:|-----------:|-------------------:|-----------------:|-------------------:|-----------:|---------------:|----------------:|------------:|-----------:|-------------------:|-----------------:|-------------------:|:-----------|
| S2_F2_30_locked_open_5 | 2023-06-27 00:00:00 | 09:35   | BUY    |     100.000000 |       23.110000 | 2312.155500 |   5.023122 |           0.000000 |        10.377869 |        1000.000000 |          0 |     nan        |      nan        |  nan        | nan        |         nan        |       nan        |         nan        | left_only  |
| S2_F2_30_locked_open_5 | 2023-06-28 00:00:00 | 09:25   | BUY    |     nan        |      nan        |  nan        | nan        |         nan        |       nan        |         nan        |          0 |     100.000000 |       21.990000 | 2200.099500 |   5.022001 |           0.000000 |       122.434990 |        1000.000000 | right_only |

## S1_F1 paid annual attribution

| scenario                  |   year |   increment_cash |        fees |   dividend_tax |   sales |   deficit_days |   ending_relative |
|:--------------------------|-------:|-----------------:|------------:|---------------:|--------:|---------------:|------------------:|
| S1_F1_30_paid_open_5      |   2020 |       354.526058 | 1309.443942 |       0.000000 |      51 |              0 |        354.526058 |
| S1_F1_30_paid_open_5      |   2021 |     -1731.513297 | 1076.583297 |      50.000000 |      46 |              0 |      -1376.987239 |
| S1_F1_30_paid_open_5      |   2022 |     -1216.300846 |  843.760846 |     100.000000 |      42 |              0 |      -2593.288085 |
| S1_F1_30_paid_open_5      |   2023 |     -1347.724570 |  715.104570 |     110.000000 |      29 |              0 |      -3941.012655 |
| S1_F1_30_paid_open_5      |   2024 |      3080.541969 |  802.893031 |     116.000000 |      37 |              0 |       -860.470686 |
| S1_F1_30_paid_open_5      |   2025 |     10487.235578 | 1464.394422 |     128.000000 |      46 |              0 |       9626.764892 |
| S1_F1_30_paid_open_5      |   2026 |      1644.642365 | 1757.747635 |     196.000000 |      35 |              0 |      11271.407257 |
| S1_F1_30_paid_open_10     |   2020 |      -411.116684 | 1309.056684 |       0.000000 |      51 |              0 |       -411.116684 |
| S1_F1_30_paid_open_10     |   2021 |     -2326.149394 | 1076.289394 |      50.000000 |      46 |              0 |      -2737.266078 |
| S1_F1_30_paid_open_10     |   2022 |     -1628.634492 |  843.554492 |     100.000000 |      42 |              0 |      -4365.900570 |
| S1_F1_30_paid_open_10     |   2023 |     -1830.136740 |  714.896740 |     110.000000 |      29 |              0 |      -6196.037310 |
| S1_F1_30_paid_open_10     |   2024 |      2250.185238 |  802.684762 |     116.000000 |      37 |              0 |      -3945.852072 |
| S1_F1_30_paid_open_10     |   2025 |      8787.293310 | 1463.966690 |     128.000000 |      46 |              0 |       4841.441239 |
| S1_F1_30_paid_open_10     |   2026 |      -576.411082 | 1757.191082 |     196.000000 |      35 |              0 |       4265.030157 |
| S1_F1_30_paid_post0935_5  |   2020 |      1094.910866 | 1309.429134 |       0.000000 |      51 |              0 |       1094.910866 |
| S1_F1_30_paid_post0935_5  |   2021 |     -2381.851303 | 1076.596304 |      50.000000 |      46 |              0 |      -1286.940438 |
| S1_F1_30_paid_post0935_5  |   2022 |     -1806.600949 |  843.765949 |     100.000000 |      42 |              0 |      -3093.541386 |
| S1_F1_30_paid_post0935_5  |   2023 |      -187.132964 |  715.092964 |     110.000000 |      29 |              0 |      -3280.674351 |
| S1_F1_30_paid_post0935_5  |   2024 |      3500.756171 |  802.888829 |     116.000000 |      37 |              0 |        220.081820 |
| S1_F1_30_paid_post0935_5  |   2025 |      8345.854267 | 1464.705733 |     128.000000 |      46 |              0 |       8565.936087 |
| S1_F1_30_paid_post0935_5  |   2026 |      -466.719582 | 1758.054582 |     196.000000 |      35 |              0 |       8099.216505 |
| S1_F1_30_paid_post0935_10 |   2020 |       329.638131 | 1309.041869 |       0.000000 |      51 |              0 |        329.638131 |
| S1_F1_30_paid_post0935_10 |   2021 |     -2976.812407 | 1076.302407 |      50.000000 |      46 |              0 |      -2647.174276 |
| S1_F1_30_paid_post0935_10 |   2022 |     -2219.229597 |  843.559597 |     100.000000 |      42 |              0 |      -4866.403873 |
| S1_F1_30_paid_post0935_10 |   2023 |      -668.965129 |  714.885129 |     110.000000 |      29 |              0 |      -5535.369002 |
| S1_F1_30_paid_post0935_10 |   2024 |      2670.609443 |  802.680558 |     116.000000 |      37 |              0 |      -2864.759559 |
| S1_F1_30_paid_post0935_10 |   2025 |      6644.841843 | 1464.278157 |     128.000000 |      46 |              0 |       3780.082284 |
| S1_F1_30_paid_post0935_10 |   2026 |     -2688.828183 | 1757.498183 |     196.000000 |      35 |              0 |       1091.254101 |

## S1_F1 locked annual attribution

| scenario                    |   year |   increment_cash |        fees |   dividend_tax |   sales |   deficit_days |   ending_relative |
|:----------------------------|-------:|-----------------:|------------:|---------------:|--------:|---------------:|------------------:|
| S1_F1_30_locked_open_5      |   2020 |       354.526058 | 1309.443942 |       0.000000 |      51 |              0 |        354.526058 |
| S1_F1_30_locked_open_5      |   2021 |     -1731.513297 | 1076.583297 |      50.000000 |      46 |              0 |      -1376.987239 |
| S1_F1_30_locked_open_5      |   2022 |     -1216.300846 |  843.760846 |     100.000000 |      42 |              0 |      -2593.288085 |
| S1_F1_30_locked_open_5      |   2023 |     -1347.724570 |  715.104570 |     110.000000 |      29 |              0 |      -3941.012655 |
| S1_F1_30_locked_open_5      |   2024 |      3080.541969 |  802.893031 |     116.000000 |      37 |              0 |       -860.470686 |
| S1_F1_30_locked_open_5      |   2025 |     10487.235578 | 1464.394422 |     128.000000 |      46 |              0 |       9626.764892 |
| S1_F1_30_locked_open_5      |   2026 |      1644.642365 | 1757.747635 |     196.000000 |      35 |              0 |      11271.407257 |
| S1_F1_30_locked_open_10     |   2020 |      -411.116684 | 1309.056684 |       0.000000 |      51 |              0 |       -411.116684 |
| S1_F1_30_locked_open_10     |   2021 |     -2326.149394 | 1076.289394 |      50.000000 |      46 |              0 |      -2737.266078 |
| S1_F1_30_locked_open_10     |   2022 |     -1628.634492 |  843.554492 |     100.000000 |      42 |              0 |      -4365.900570 |
| S1_F1_30_locked_open_10     |   2023 |     -1487.414323 |  689.221323 |     110.000000 |      27 |             27 |      -5853.314892 |
| S1_F1_30_locked_open_10     |   2024 |     -1165.704913 |   39.060913 |       0.000000 |       2 |            231 |      -7019.019806 |
| S1_F1_30_locked_open_10     |   2025 |     -4066.800000 |    0.000000 |       0.000000 |       0 |            243 |     -11085.819806 |
| S1_F1_30_locked_open_10     |   2026 |      -300.000000 |    0.000000 |       0.000000 |       0 |            169 |     -11385.819806 |
| S1_F1_30_locked_post0935_5  |   2020 |      1094.910866 | 1309.429134 |       0.000000 |      51 |              0 |       1094.910866 |
| S1_F1_30_locked_post0935_5  |   2021 |     -2381.851303 | 1076.596304 |      50.000000 |      46 |              0 |      -1286.940438 |
| S1_F1_30_locked_post0935_5  |   2022 |     -1806.600949 |  843.765949 |     100.000000 |      42 |              0 |      -3093.541386 |
| S1_F1_30_locked_post0935_5  |   2023 |      -187.132964 |  715.092964 |     110.000000 |      29 |              0 |      -3280.674351 |
| S1_F1_30_locked_post0935_5  |   2024 |      3500.756171 |  802.888829 |     116.000000 |      37 |              0 |        220.081820 |
| S1_F1_30_locked_post0935_5  |   2025 |      8345.854267 | 1464.705733 |     128.000000 |      46 |              0 |       8565.936087 |
| S1_F1_30_locked_post0935_5  |   2026 |      -466.719582 | 1758.054582 |     196.000000 |      35 |              0 |       8099.216505 |
| S1_F1_30_locked_post0935_10 |   2020 |       329.638131 | 1309.041869 |       0.000000 |      51 |              0 |        329.638131 |
| S1_F1_30_locked_post0935_10 |   2021 |     -2976.812407 | 1076.302407 |      50.000000 |      46 |              0 |      -2647.174276 |
| S1_F1_30_locked_post0935_10 |   2022 |     -2219.229597 |  843.559597 |     100.000000 |      42 |              0 |      -4866.403873 |
| S1_F1_30_locked_post0935_10 |   2023 |     -1254.581432 |  227.149432 |       0.000000 |      10 |            170 |      -6120.985305 |
| S1_F1_30_locked_post0935_10 |   2024 |      -646.500000 |    0.000000 |       0.000000 |       0 |            242 |      -6767.485305 |
| S1_F1_30_locked_post0935_10 |   2025 |     -4119.000000 |    0.000000 |       0.000000 |       0 |            243 |     -10886.485305 |
| S1_F1_30_locked_post0935_10 |   2026 |      -300.000000 |    0.000000 |       0.000000 |       0 |            169 |     -11186.485305 |

## S1_F1 paid largest negative original events

| scenario                  |   original_event |   increment_cash | start      | end        | method                                                                                                     |
|:--------------------------|-----------------:|-----------------:|:-----------|:-----------|:-----------------------------------------------------------------------------------------------------------|
| S1_F1_30_paid_open_10     |               99 |     -4930.585318 | 2026-03-10 | 2026-05-11 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |               99 |     -4378.297754 | 2026-03-10 | 2026-05-11 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               95 |     -3457.941472 | 2025-12-18 | 2026-01-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_5  |               95 |     -3332.997101 | 2025-12-18 | 2026-01-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               99 |     -2908.271316 | 2026-03-10 | 2026-05-11 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_5  |               99 |     -2356.993899 | 2026-03-10 | 2026-05-11 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               85 |     -1874.936811 | 2025-04-22 | 2025-05-29 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_5  |               85 |     -1781.554955 | 2025-04-22 | 2025-05-29 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_10     |               95 |     -1515.719114 | 2025-12-18 | 2026-01-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_10     |               85 |     -1394.452006 | 2025-04-22 | 2025-05-29 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |               95 |     -1391.744884 | 2025-12-18 | 2026-01-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |               85 |     -1301.310153 | 2025-04-22 | 2025-05-29 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |

## S1_F1 paid largest positive original events

| scenario                  |   original_event |   increment_cash | start      | end        | method                                                                                                     |
|:--------------------------|-----------------:|-----------------:|:-----------|:-----------|:-----------------------------------------------------------------------------------------------------------|
| S1_F1_30_paid_post0935_5  |               92 |     11216.975784 | 2025-10-16 | 2025-11-28 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               92 |     10725.631043 | 2025-10-16 | 2025-11-28 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |               92 |      8875.465378 | 2025-10-16 | 2025-11-28 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_10     |               92 |      8382.950467 | 2025-10-16 | 2025-11-28 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_5  |               96 |      3512.263924 | 2026-01-12 | 2026-01-30 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               96 |      3327.585879 | 2026-01-12 | 2026-01-30 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |              100 |      2211.521016 | 2026-05-12 | 2026-07-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_5  |               98 |      2007.599575 | 2026-02-26 | 2026-03-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_post0935_10 |               98 |      1950.719216 | 2026-02-26 | 2026-03-09 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_5      |                1 |      1949.079107 | 2020-01-10 | 2020-02-10 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_10     |               91 |      1874.622718 | 2025-09-23 | 2025-10-15 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |
| S1_F1_30_paid_open_10     |                1 |      1856.051214 | 2020-01-10 | 2020-02-10 | daily relative change assigned to latest actual sale original event; residual holding attribution retained |

## C independently mismatching price cases

| scenario                   | date       | clock   |   quantity |   reference | fine_price_available   |   price_gap | price_status                | fill_status                                 |
|:---------------------------|:-----------|:--------|-----------:|------------:|:-----------------------|------------:|:----------------------------|:--------------------------------------------|
| S1_F1_30_paid_post0935_5   | 2026-05-15 | 09:40   |       1000 |   70.600000 | True                   |    0.159998 | disagrees_with_qualified_1m | unproven_auction_queue_receipt_and_capacity |
| S1_F1_30_paid_post0935_10  | 2026-05-15 | 09:40   |       1000 |   70.600000 | True                   |    0.159998 | disagrees_with_qualified_1m | unproven_auction_queue_receipt_and_capacity |
| S1_F1_30_locked_post0935_5 | 2026-05-15 | 09:40   |       1000 |   70.600000 | True                   |    0.159998 | disagrees_with_qualified_1m | unproven_auction_queue_receipt_and_capacity |

## B matched/unmatched1m aggregate

| fine_qualified   | original_signal   |    n |      mean |          cash |
|:-----------------|:------------------|-----:|----------:|--------------:|
| False            | False             | 1141 | -0.208656 | -28422.934255 |
| False            | True              |  386 | -0.035448 |   4570.566218 |
| True             | False             |   67 | -0.333175 | -15098.141089 |
| True             | True              |   25 |  0.225267 |   5174.865196 |

## B QC flag counts on original411

| flag           |   count |
|:---------------|--------:|
| endpoint_good  |     411 |
| high_bad       |      84 |
| low_bad        |      39 |
| volume_bad     |      65 |
| strict         |     270 |
| fine_qualified |      25 |