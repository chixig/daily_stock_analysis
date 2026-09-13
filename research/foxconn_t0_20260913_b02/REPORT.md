# 反T第二批：假设覆盖与失败原因复核

事实：全部计算在GitHub；数据至2026-09-11；六个预登记假设×四阶段，无参数扩展。

## 覆盖边界

| family                                    | stages   | evidence                                | boundary                                                      |
|:------------------------------------------|:---------|:----------------------------------------|:--------------------------------------------------------------|
| single day returns/volume/candle/location | all4     | batch01 88 regions                      | covered narrowly; not exhaustive                              |
| multi-day failed breakout                 | all4     | batch02 fixed definition                | tested; exact daily failure, not intraday breakout            |
| weak rebound under MA20                   | all4     | batch02 fixed definition                | tested; structural zero cells remain                          |
| 3day volume without price progress        | all4     | batch02 fixed definition                | tested; no threshold tuning                                   |
| stock/index previous-day divergence       | all4     | batch02 fixed definition                | tested                                                        |
| opening gap interactions                  | all4     | batch02 two fixed events                | benchmark and after-open indicative prices split              |
| intraday reversal/TP/SL                   | all4     | old E1 failure; first batch fixed times | not comprehensively tested; cannot infer fills from snapshots |
| announcements/industry/US shocks          | all4     | historical partial evidence only        | not covered this batch; needs point-in-time event data        |
| auction imbalance/orderflow               | all4     | no orderbook data                       | unavailable, not falsified                                    |
| true future validation                    | all4     | no future samples                       | not started; never substitute historic resampling             |

## 24个研究单元

| id                 |   n |   mean_pct |       cash |   coverage_pct |   new_n |   new_cash |   2024_pct |   2025_pct |   2026_ytd_pct | decision_time   |   indicative_0935_pct |
|:-------------------|----:|-----------:|-----------:|---------------:|--------:|-----------:|-----------:|-----------:|---------------:|:----------------|----------------------:|
| U__failed_breakout |  25 |     -1.310 |  -9112.623 |         11.574 |      23 | -10744.748 |     -1.503 |     -1.877 |          1.971 | previous_close  |                -0.780 |
| U__failed_rebound  |   0 |    nan     |      0.000 |          0.000 |       0 |      0.000 |    nan     |    nan     |        nan     | previous_close  |               nan     |
| U__distribution3   |  13 |     -1.294 |  -5878.062 |          6.019 |      11 |  -5118.937 |     -2.706 |     -0.925 |         -0.342 | previous_close  |                -1.307 |
| U__relative_weak   |  36 |     -0.484 |  -5342.538 |         16.667 |      36 |  -5342.538 |      0.352 |     -1.242 |          1.479 | previous_close  |                -0.155 |
| U__gapdown_red     |  30 |     -0.962 | -17913.217 |         13.889 |      29 | -17788.571 |      0.650 |     -2.372 |         -0.360 | after_open      |                -0.475 |
| U__gapup_weak      |  18 |     -0.581 |  -6728.389 |          8.333 |      16 |  -9174.655 |     -0.304 |     -0.126 |         -1.479 | after_open      |                -0.643 |
| R__failed_breakout |   1 |     -6.954 |  -1759.322 |          0.658 |       0 |      0.000 |     -6.954 |    nan     |        nan     | previous_close  |                -6.243 |
| R__failed_rebound  |  17 |      0.042 |   1279.349 |         11.184 |      16 |   1036.435 |      0.020 |     -0.482 |          2.213 | previous_close  |                 0.043 |
| R__distribution3   |   8 |     -1.242 |  -4931.361 |          5.263 |       6 |  -4222.654 |     -0.397 |     -2.649 |        nan     | previous_close  |                -0.464 |
| R__relative_weak   |  27 |     -0.705 |  -9807.297 |         17.763 |      25 |  -9699.135 |     -0.265 |     -0.952 |         -1.330 | previous_close  |                -0.758 |
| R__gapdown_red     |  18 |     -0.208 |    269.588 |         11.842 |      18 |    269.588 |     -0.166 |     -0.959 |          0.180 | after_open      |                -0.505 |
| R__gapup_weak      |  16 |     -1.677 | -11913.210 |         10.526 |      16 | -11913.210 |     -1.944 |     -2.439 |         -0.901 | after_open      |                -1.541 |
| D__failed_breakout |   0 |    nan     |      0.000 |          0.000 |       0 |      0.000 |    nan     |    nan     |        nan     | previous_close  |               nan     |
| D__failed_rebound  |  24 |     -0.656 |  -7372.148 |         14.458 |      24 |  -7372.148 |      0.173 |     -1.451 |         -1.046 | previous_close  |                -0.252 |
| D__distribution3   |  15 |     -0.805 |  -1465.800 |          9.036 |      15 |  -1465.800 |      0.626 |     -4.568 |          0.395 | previous_close  |                -0.669 |
| D__relative_weak   |  37 |     -0.831 |  -8119.788 |         22.289 |      37 |  -8119.788 |     -1.192 |     -0.934 |         -0.478 | previous_close  |                -0.535 |
| D__gapdown_red     |  24 |     -0.857 |  -3875.920 |         14.458 |      24 |  -3875.920 |     -0.374 |     -3.783 |         -0.188 | after_open      |                -0.277 |
| D__gapup_weak      |  24 |     -0.445 |  -4949.546 |         14.458 |      24 |  -4949.546 |     -0.113 |     -0.598 |         -0.572 | after_open      |                -0.306 |
| C__failed_breakout |  10 |     -0.772 |  -1957.102 |          8.333 |      10 |  -1957.102 |     -1.449 |     -0.476 |         -0.487 | previous_close  |                -0.915 |
| C__failed_rebound  |   1 |      0.866 |    522.436 |          0.833 |       1 |    522.436 |    nan     |    nan     |          0.866 | previous_close  |                 0.005 |
| C__distribution3   |   7 |      0.796 |    303.581 |          5.833 |       7 |    303.581 |      1.454 |     -0.083 |        nan     | previous_close  |                 0.037 |
| C__relative_weak   |  20 |     -0.300 |  -4310.533 |         16.667 |      20 |  -4310.533 |      2.006 |     -1.574 |         -0.730 | previous_close  |                -0.380 |
| C__gapdown_red     |  11 |     -0.003 |  -1064.020 |          9.167 |      11 |  -1064.020 |      1.261 |      0.148 |         -1.103 | after_open      |                 0.120 |
| C__gapup_weak      |  12 |     -1.513 |  -7070.382 |         10.000 |      12 |  -7070.382 |     -0.550 |     -1.689 |         -1.717 | after_open      |                -1.352 |

## 正收益区域的历史反证

| id                |   n |   mean_pct |   block_low |   block_high |   delete_top3_pct |   new_mean_pct |   indicative_0935_cash |
|:------------------|----:|-----------:|------------:|-------------:|------------------:|---------------:|-----------------------:|
| R__failed_rebound |  17 |      0.042 |      -0.799 |        1.029 |            -0.620 |         -0.018 |                230.630 |
| C__failed_rebound |   1 |      0.866 |       0.866 |        0.866 |           nan     |          0.866 |                  3.032 |
| C__distribution3  |   7 |      0.796 |      -1.175 |        2.490 |            -1.311 |          0.796 |                193.547 |

## 原候选集中度

| candidate      |   n |   losers |   best3_cash_share_of_positive |   max_single_topup |   exclude_2024_cash |   exclude_2025_cash |   exclude_2026_cash |
|:---------------|----:|---------:|-------------------------------:|-------------------:|--------------------:|--------------------:|--------------------:|
| UR_VOL_frozen  |  23 |        9 |                          0.576 |           1759.322 |            7323.618 |            7851.291 |            2237.499 |
| UR_VOL_v3      |  31 |       12 |                          0.433 |           1759.322 |           11171.327 |           10550.153 |            4851.591 |
| R_deceleration |  15 |        4 |                          0.610 |           1237.858 |            1205.717 |            6076.097 |            3072.794 |

## 原候选事前字段分组（诊断，不自动过滤）

| candidate      | tag             |   n |   mean_pct |      cash |   worst_pct |
|:---------------|:----------------|----:|-----------:|----------:|------------:|
| UR_VOL_frozen  | gap_negative    |  12 |      0.511 |  2462.926 |      -6.954 |
| UR_VOL_frozen  | gap_nonnegative |  11 |      1.139 |  6243.277 |      -2.341 |
| UR_VOL_frozen  | clv_lt04        |   5 |      0.982 |  2213.458 |      -0.623 |
| UR_VOL_frozen  | clv_ge04        |  18 |      0.764 |  6492.746 |      -6.954 |
| UR_VOL_frozen  | year2024        |   9 |      0.669 |  1382.586 |      -6.954 |
| UR_VOL_frozen  | year2025        |   9 |      0.401 |   854.913 |      -2.341 |
| UR_VOL_frozen  | year2026        |   5 |      1.806 |  6468.705 |      -1.583 |
| UR_VOL_v3      | gap_negative    |  17 |      1.035 |  7188.855 |      -6.954 |
| UR_VOL_v3      | gap_nonnegative |  14 |      0.824 |  6097.680 |      -2.827 |
| UR_VOL_v3      | clv_lt04        |   6 |      1.239 |  2732.498 |      -0.623 |
| UR_VOL_v3      | clv_ge04        |  25 |      0.868 | 10554.038 |      -6.954 |
| UR_VOL_v3      | year2024        |  13 |      0.711 |  2115.209 |      -6.954 |
| UR_VOL_v3      | year2025        |  10 |      0.767 |  2736.382 |      -2.341 |
| UR_VOL_v3      | year2026        |   8 |      1.527 |  8434.945 |      -1.583 |
| R_deceleration | gap_negative    |  10 |      0.924 |  3651.347 |      -1.500 |
| R_deceleration | gap_nonnegative |   5 |      1.786 |  1525.957 |      -2.069 |
| R_deceleration | clv_lt04        |   7 |      1.290 |  3534.132 |      -0.478 |
| R_deceleration | clv_ge04        |   8 |      1.143 |  1643.172 |      -2.069 |
| R_deceleration | year2024        |   9 |      1.752 |  3971.587 |      -1.500 |
| R_deceleration | year2025        |   5 |     -0.165 |  -898.793 |      -2.069 |
| R_deceleration | year2026        |   1 |      3.223 |  2104.510 |       3.223 |

## 最大亏损与盈利个案

| candidate      | kind   | date       |   rt_cash |   rt_pct |    gap |    vr |   clv |      r3 |
|:---------------|:-------|:-----------|----------:|---------:|-------:|------:|------:|--------:|
| UR_VOL_frozen  | worst  | 2024-11-11 | -1759.322 |   -6.954 | -2.617 | 2.164 | 0.514 |   4.970 |
| UR_VOL_frozen  | worst  | 2026-04-23 | -1060.538 |   -1.583 |  0.135 | 1.839 | 0.899 |   9.710 |
| UR_VOL_frozen  | worst  | 2026-06-22 |  -940.323 |   -1.204 |  0.000 | 1.678 | 0.771 |   6.376 |
| UR_VOL_frozen  | worst  | 2024-03-15 |  -634.480 |   -2.821 | -1.575 | 1.969 | 0.672 | -11.503 |
| UR_VOL_frozen  | worst  | 2025-07-04 |  -545.680 |   -2.341 |  0.129 | 3.381 | 1.000 |   8.887 |
| UR_VOL_frozen  | best   | 2026-05-14 |  5270.985 |    7.123 |  4.461 | 1.717 | 1.000 |  11.947 |
| UR_VOL_frozen  | best   | 2026-05-15 |  1756.770 |    2.528 |  1.312 | 1.603 | 0.196 |   4.176 |
| UR_VOL_frozen  | best   | 2026-04-24 |  1441.810 |    2.166 | -1.988 | 1.548 | 0.516 |  10.421 |
| UR_VOL_frozen  | best   | 2024-06-07 |  1271.388 |    4.918 | -0.844 | 2.160 | 1.000 |   9.217 |
| UR_VOL_frozen  | best   | 2024-11-12 |  1239.609 |    4.589 |  0.000 | 1.936 | 0.914 |  11.704 |
| UR_VOL_v3      | worst  | 2024-11-11 | -1759.322 |   -6.954 | -2.617 | 2.164 | 0.514 |   4.970 |
| UR_VOL_v3      | worst  | 2026-04-23 | -1060.538 |   -1.583 |  0.135 | 1.839 | 0.899 |   9.710 |
| UR_VOL_v3      | worst  | 2026-06-22 |  -940.323 |   -1.204 |  0.000 | 1.678 | 0.771 |   6.376 |
| UR_VOL_v3      | worst  | 2024-03-15 |  -634.480 |   -2.821 | -1.575 | 1.969 | 0.672 | -11.503 |
| UR_VOL_v3      | worst  | 2025-07-04 |  -545.680 |   -2.341 |  0.129 | 3.381 | 1.000 |   8.887 |
| UR_VOL_v3      | best   | 2026-05-14 |  5270.985 |    7.123 |  4.461 | 1.717 | 1.000 |  11.947 |
| UR_VOL_v3      | best   | 2026-05-15 |  1756.770 |    2.528 |  1.312 | 1.603 | 0.196 |   4.176 |
| UR_VOL_v3      | best   | 2025-12-10 |  1511.372 |    2.261 | -1.691 | 1.545 | 0.925 |  10.733 |
| UR_VOL_v3      | best   | 2026-04-24 |  1441.810 |    2.166 | -1.988 | 1.548 | 0.516 |  10.421 |
| UR_VOL_v3      | best   | 2026-09-08 |  1432.287 |    2.160 | -0.406 | 1.513 | 0.864 |   7.718 |
| R_deceleration | worst  | 2025-12-02 | -1237.858 |   -2.069 |  0.033 | 1.013 | 0.819 |   1.493 |
| R_deceleration | worst  | 2024-04-16 |  -322.863 |   -1.500 | -3.192 | 0.652 | 0.635 |   5.403 |
| R_deceleration | worst  | 2025-03-18 |  -102.675 |   -0.478 | -0.186 | 0.815 | 0.342 |   2.917 |
| R_deceleration | worst  | 2025-06-03 |    -8.586 |   -0.046 | -0.581 | 1.222 | 0.000 |   2.491 |
| R_deceleration | worst  | 2025-12-01 |   112.655 |    0.188 | -1.136 | 0.926 | 0.977 |   7.260 |
| R_deceleration | best   | 2026-07-13 |  2104.510 |    3.223 | -1.464 | 1.064 | 0.015 |   3.904 |
| R_deceleration | best   | 2024-11-12 |  1239.609 |    4.589 |  0.000 | 1.936 | 0.914 |  11.704 |
| R_deceleration | best   | 2024-11-15 |   832.759 |    3.358 | -0.281 | 1.056 | 0.011 |  -7.923 |
| R_deceleration | best   | 2024-04-30 |   751.958 |    2.972 |  3.181 | 1.437 | 0.593 |  10.252 |
| R_deceleration | best   | 2024-12-09 |   445.873 |    1.971 |  0.088 | 0.798 | 0.841 |   1.619 |

## 反方向候选

| id                 |   n |   rt_pct |   pt_pct |   pt_cash |
|:-------------------|----:|---------:|---------:|----------:|
| U__failed_breakout |  25 |   -1.310 |    0.937 |  5183.804 |
| U__distribution3   |  13 |   -1.294 |    0.916 |  3719.539 |
| U__gapdown_red     |  30 |   -0.962 |    0.591 | 12779.115 |
| U__gapup_weak      |  18 |   -0.581 |    0.202 |  4108.903 |
| R__failed_breakout |   1 |   -6.954 |    6.561 |  1659.824 |
| R__distribution3   |   8 |   -1.242 |    0.857 |  3866.441 |
| R__relative_weak   |  27 |   -0.705 |    0.326 |  5968.761 |
| R__gapup_weak      |  16 |   -1.677 |    1.304 |  9021.559 |
| D__failed_rebound  |  24 |   -0.656 |    0.266 |  4424.904 |
| D__distribution3   |  15 |   -0.805 |    0.402 |   -66.150 |
| D__relative_weak   |  37 |   -0.831 |    0.442 |  3157.394 |
| D__gapdown_red     |  24 |   -0.857 |    0.468 |   742.926 |
| C__failed_breakout |  10 |   -0.772 |    0.388 |   582.264 |
| C__gapup_weak      |  12 |   -1.513 |    1.130 |  5346.515 |

## 路径诊断（非止盈止损回测）

| candidate      |   n |   best1_share_net |   best3_share_net |   year2026_share_net |   path_valid_n |   loser_n |   loser_touched_favorable1 |   loser_touched_adverse2 |   loser_adverse_before_favorable |   loser_same_bar_unknown |   winner_n |   winner_touched_favorable1 |   winner_touched_adverse2 |   winner_adverse_before_favorable |   winner_same_bar_unknown |
|:---------------|----:|------------------:|------------------:|---------------------:|---------------:|----------:|---------------------------:|-------------------------:|---------------------------------:|-------------------------:|-----------:|----------------------------:|--------------------------:|----------------------------------:|--------------------------:|
| UR_VOL_frozen  |  23 |             0.605 |             0.973 |                0.743 |             23 |         9 |                          3 |                        7 |                                7 |                        0 |         14 |                          14 |                         2 |                                 1 |                         0 |
| UR_VOL_v3      |  31 |             0.397 |             0.643 |                0.635 |             31 |        12 |                          4 |                        8 |                                8 |                        0 |         19 |                          19 |                         3 |                                 2 |                         0 |
| R_deceleration |  15 |             0.406 |             0.807 |                0.406 |             15 |         4 |                          0 |                        2 |                                2 |                        0 |         11 |                          11 |                         1 |                                 1 |                         0 |

固定诊断线为向下1%有利空间、向上2%不利空间；同5分钟bar不判断先后，触价不等于成交。阈值只作失败归因描述，不新建优化策略。

## 解释限制

亏损交易的MAE/MFE只用于事后路径描述，不可拿来作为当时知道的过滤条件。开盘后指示价不是成交认证。

24个单元不是24条独立策略；六类机制的定义可能交叠。区间是历史描述，未校正历次选择；零样本不是机制失败。

没有采用自适应止损或追加条件，没有升级正T，正T仅双向登记。未启动实际交易、前瞻自动化或隔夜。

## 验证

父批次输入哈希、现金流确定性测试、前日假设的当日OHLC及成交量变动不影响当日信号测试通过。

指数可用=True；全部行及失败记录见results。