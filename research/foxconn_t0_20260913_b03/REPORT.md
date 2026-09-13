# Foxconn batch03: factor audit and intraday/overnight attribution

All data processing on GitHub. Data through 2026-09-11. Historical research, not actual trading.

## Audit

{
  "factor_n": 38,
  "rule_n": 410,
  "nonempty": 392,
  "n30": 239,
  "basic_pass": 0,
  "statistical_pass": 0,
  "literal_open_pass": 0,
  "negative_mean": 322,
  "large_negative": 229,
  "input_hashes": {
    "research/foxconn_t0_20260913/results/daily_features_and_cashflows.csv": "336fd19b75d4489db11fbee4ac084744b6ea0c16802b3183bb128c43fd547e85",
    "research/foxconn_t0_20260913/source/601138-full-5min-history.zip": "6decd5fbe5916d974d7897f9259de6dbe0c319722bd3972a85d780cf25c1c5ff",
    "research/foxconn_t0_20260913_b02/source/sse_index.csv": "108cf1e67314f5c972ce064f39793368215a532ee701d6504a876a2c11d41c9c"
  },
  "feature_mutation_tests": "passed at 3 historical cutoffs",
  "stage_match": true,
  "attribution_identity": "passed 1e-12",
  "minute_primary_valid": 651,
  "US": [
    {
      "series": "NASDAQCOM",
      "status": "available",
      "rows": 2185,
      "attempts": [
        {
          "provider": "Yahoo same Nasdaq index",
          "status": "available",
          "source": "https://query1.finance.yahoo.com/v8/finance/chart/%5EIXIC?period1=1514764800&period2=1789171200&interval=1d"
        }
      ],
      "vintage": "current vendor, not publication-vintage certified"
    },
    {
      "series": "NASDAQSOX",
      "status": "available",
      "rows": 2185,
      "attempts": [
        {
          "provider": "Yahoo same Nasdaq index",
          "status": "available",
          "source": "https://query1.finance.yahoo.com/v8/finance/chart/%5ESOX?period1=1514764800&period2=1789171200&interval=1d"
        }
      ],
      "vintage": "current vendor, not publication-vintage certified"
    }
  ],
  "limitations": [
    "history already inspected",
    "current vendor vintage",
    "within-batch multiplicity only",
    "bar proxy not fills",
    "PT direction layer, not discretionary implementation"
  ]
}

## Highest RT means among N>=30, not validated recommendations

| id                       |   n |   mean_pct |      cash |   pf_cash |   2024_pct |   2025_pct |   2026_pct |   delete5_pct |   delayed_pct |   maxT_p | basic_pass   |
|:-------------------------|----:|-----------:|----------:|----------:|-----------:|-----------:|-----------:|--------------:|--------------:|---------:|:-------------|
| C__clv__high             |  37 |      0.546 |  4051.069 |     1.274 |      0.586 |      1.462 |     -0.339 |        -0.062 |         0.230 |    0.977 | False        |
| C__amihud20__high        |  30 |      0.371 |  5141.667 |     1.603 |    nan     |      0.274 |      0.516 |        -0.226 |         0.098 |  nan     | False        |
| U__combo_exhaustion      |  31 |      0.358 |  9960.837 |     1.610 |      0.833 |     -0.746 |      1.886 |        -0.754 |         0.225 |    1.000 | False        |
| R__upper_shadow__low     |  36 |      0.340 |  4499.633 |     1.374 |      0.540 |     -0.271 |      0.471 |        -0.334 |        -0.119 |    0.994 | False        |
| C__range_pos20__high     |  34 |      0.316 |  7064.543 |     1.901 |     -0.991 |      1.766 |      0.543 |        -0.315 |         0.035 |  nan     | False        |
| C__market_ret5__high     |  45 |      0.252 |  4791.357 |     1.313 |      0.351 |     -0.068 |      0.447 |        -0.297 |         0.116 |    1.000 | False        |
| C__market_ret1__high     |  41 |      0.241 |   748.311 |     1.053 |      0.008 |      1.131 |     -0.207 |        -0.377 |        -0.000 |    1.000 | False        |
| C__volume_ratio__high    |  39 |      0.236 |  1049.689 |     1.076 |      0.169 |      0.617 |     -0.019 |        -0.383 |         0.134 |    1.000 | False        |
| C__beta_residual1__high  |  31 |      0.228 |  2657.551 |     1.248 |      0.277 |      0.414 |     -0.100 |        -0.532 |         0.137 |    1.000 | False        |
| ALL__combo_exhaustion    |  60 |      0.175 | 11132.554 |     1.412 |      0.329 |     -0.444 |      0.806 |        -0.417 |         0.050 |    1.000 | False        |
| C__ret10__high           |  30 |      0.147 | -1147.008 |     0.917 |     -0.063 |      1.766 |     -1.103 |        -0.665 |        -0.248 |  nan     | False        |
| C__bias5__high           |  43 |      0.134 |  5165.812 |     1.358 |     -0.660 |      1.167 |      0.343 |        -0.470 |         0.193 |    1.000 | False        |
| C__ret3__high            |  44 |      0.124 |  4112.862 |     1.258 |     -0.549 |      1.034 |      0.024 |        -0.466 |         0.123 |    1.000 | False        |
| C__prev_am_return__high  |  35 |      0.100 | -2767.906 |     0.832 |      0.460 |      0.243 |     -0.736 |        -0.616 |         0.011 |    1.000 | False        |
| C__range_expansion__high |  34 |      0.094 |  2376.624 |     1.256 |     -0.163 |      0.903 |     -0.377 |        -0.598 |         0.126 |  nan     | False        |

## Causal-stage return attribution (primary)

| window   | label   | stage   |   n |   previous20_mean_pct |   day_mean_log_bp |   day_linked_pct |   night_mean_log_bp |   night_linked_pct |   intraday_mean_log_bp |   intraday_linked_pct |   raw_night_mean_log_bp |   raw_night_linked_pct |   action_mean_log_bp |   action_linked_pct |   daily_down_pct |   intraday_down_pct |   night_down_pct |   rt_net_mean_pct |   pt_net_mean_pct |   gross_rt_arith_mean_pct |   remove5_worst_daily_mean_log_bp |
|:---------|:--------|:--------|----:|----------------------:|------------------:|-----------------:|--------------------:|-------------------:|-----------------------:|----------------------:|------------------------:|-----------------------:|---------------------:|--------------------:|-----------------:|--------------------:|-----------------:|------------------:|------------------:|--------------------------:|----------------------------------:|
| primary  | stage   | ALL     | 654 |                 6.491 |            23.056 |          351.702 |             -12.953 |            -57.137 |                 36.009 |               953.818 |                 -13.930 |                -59.790 |               -0.977 |              -6.190 |           50.000 |              48.165 |           52.446 |            -0.602 |             0.220 |                    -0.411 |                            30.655 |
| primary  | stage   | U       | 216 |                26.757 |            41.066 |          142.790 |             -17.719 |            -31.800 |                 58.785 |               255.995 |                 -18.618 |                -33.111 |               -0.899 |              -1.923 |           50.000 |              49.074 |           54.167 |            -0.846 |             0.470 |                    -0.658 |                            60.071 |
| primary  | stage   | R       | 152 |                -3.161 |            33.356 |           66.033 |              -6.543 |             -9.466 |                 39.899 |                83.393 |                  -6.901 |                 -9.958 |               -0.358 |              -0.543 |           46.053 |              42.763 |           47.368 |            -0.633 |             0.252 |                    -0.443 |                            59.838 |
| primary  | stage   | D       | 166 |               -11.173 |            -0.099 |           -0.164 |             -25.756 |            -34.789 |                 25.657 |                53.098 |                 -28.107 |                -37.285 |               -2.351 |              -3.828 |           53.012 |              49.398 |           57.229 |            -0.490 |             0.099 |                    -0.295 |                            28.501 |
| primary  | stage   | C       | 120 |                 6.671 |             9.621 |           12.238 |               5.213 |              6.456 |                  4.407 |                 5.431 |                   5.213 |                  6.456 |                0.000 |               0.000 |           50.833 |              51.667 |           49.167 |            -0.280 |            -0.105 |                    -0.088 |                            40.442 |

## Hindsight peak-trough decomposition (not tradable labels)

| peak       | trough     |   n |   decline_pct |   night_pct |   intraday_pct |   night_log_sum |   intraday_log_sum |   D_days |   non_D_days |   D_day_log |   non_D_day_log | first_D_date   |   before_first_D_days |   before_first_D_log | hindsight_only   |
|:-----------|:-----------|----:|--------------:|------------:|---------------:|----------------:|-------------------:|---------:|-------------:|------------:|----------------:|:---------------|----------------------:|---------------------:|:-----------------|
| 2020-01-22 | 2022-10-10 | 654 |       -57.312 |     -36.132 |        -33.162 |          -0.448 |             -0.403 |      206 |          448 |      -0.183 |          -0.668 | 2020-03-10     |                    27 |               -0.254 | True             |
| 2023-07-14 | 2024-01-17 | 126 |       -52.329 |     -31.386 |        -30.522 |          -0.377 |             -0.364 |       68 |           58 |      -0.100 |          -0.641 | 2023-08-24     |                    28 |               -0.220 | True             |
| 2024-07-09 | 2025-04-08 | 180 |       -45.274 |     -38.353 |        -11.227 |          -0.484 |             -0.119 |       72 |          108 |      -0.280 |          -0.323 | 2024-08-02     |                    17 |               -0.190 | True             |
| 2025-10-29 | 2026-03-23 |  95 |       -40.768 |     -36.875 |         -6.166 |          -0.460 |             -0.064 |       44 |           51 |      -0.148 |          -0.376 | 2025-12-04     |                    25 |               -0.270 | True             |
| 2026-06-03 | 2026-07-30 |  40 |       -33.621 |     -17.399 |        -19.639 |          -0.191 |             -0.219 |       10 |           30 |      -0.158 |          -0.252 | 2026-07-17     |                    30 |               -0.252 | True             |
| 2023-04-18 | 2023-05-12 |  15 |       -25.169 |      -4.912 |        -21.304 |          -0.050 |             -0.240 |        0 |           15 |       0.000 |          -0.290 |                |                    15 |               -0.290 | True             |
| 2025-09-23 | 2025-10-14 |   9 |       -15.733 |      -9.336 |         -7.056 |          -0.098 |             -0.073 |        0 |            9 |       0.000 |          -0.171 |                |                     9 |               -0.171 | True             |
| 2023-06-19 | 2023-07-12 |  15 |       -14.853 |     -12.122 |         -3.107 |          -0.129 |             -0.032 |        0 |           15 |       0.000 |          -0.161 |                |                    15 |               -0.161 | True             |

## PT versus RT, primary same q1000/cost window

|   n |   mean_pct |   median_pct |   win_pct |        cash |   pf_pct |   pf_cash |   worst_pct |    mdd_cash |   clusters |   months |   delete5_pct |   delete5_cash |   stress10bp_pct |   delayed_n |   delayed_pct |   delayed_cash |   max_cash_loss | month_ci                                    | name              | window   | direction   |
|----:|-----------:|-------------:|----------:|------------:|---------:|----------:|------------:|------------:|-----------:|---------:|--------------:|---------------:|-----------------:|------------:|--------------:|---------------:|----------------:|:--------------------------------------------|:------------------|:---------|:------------|
|  25 |      1.882 |        1.419 |    76.000 |   25033.392 |    5.004 |     4.583 |      -4.613 |   -3574.829 |         17 |       13 |         0.715 |       4957.479 |            1.781 |          24 |         1.199 |      17809.335 |       -3574.829 | [0.5217122823793049, 3.1916860681131354]    | PT_U1             | primary  | pt          |
|  14 |      2.312 |        1.890 |    85.714 |   10655.045 |   23.930 |    32.435 |      -1.212 |    -296.981 |          9 |        9 |         0.986 |       1999.934 |            2.211 |          14 |         2.211 |      11135.434 |        -296.981 | [1.3220214436407565, 3.598891466989663]     | PT_R1             | primary  | pt          |
|  20 |      0.762 |        0.754 |    65.000 |    3860.810 |    2.140 |     2.012 |      -3.419 |   -1752.504 |         13 |        9 |        -0.408 |      -1649.411 |            0.661 |          20 |        -0.059 |       -701.873 |       -1436.102 | [-0.011909758265709293, 1.7432507545775333] | PT_D1             | primary  | pt          |
|  13 |      1.667 |        2.069 |    76.923 |    5879.423 |    4.724 |     3.396 |      -2.922 |   -1822.655 |         10 |        9 |         0.295 |       -301.201 |            1.566 |          13 |         0.988 |       2157.087 |       -1822.655 | [0.6329707944926407, 3.359536301389636]     | PT_C1             | primary  | pt          |
|  72 |      1.616 |        1.429 |    75.000 |   45428.671 |    4.596 |     4.342 |      -4.613 |   -3574.829 |         42 |       29 |         1.121 |      25352.758 |            1.515 |          71 |         1.006 |      30399.983 |       -3574.829 | [0.9809582934677086, 2.3352534792265476]    | PT_PT_matrix      | primary  | pt          |
|  23 |      0.811 |        0.777 |    60.870 |    8706.204 |    2.059 |     2.451 |      -6.954 |   -1769.245 |         12 |       12 |        -0.277 |      -2274.359 |            0.712 |          23 |         1.016 |      10703.938 |       -1759.322 | [-0.2060353452688956, 2.027514401630542]    | RT_UR_volume      | primary  | rt          |
|  15 |      1.211 |        1.411 |    73.333 |    5177.304 |    5.439 |     4.097 |      -2.069 |   -1237.858 |         10 |        9 |         0.205 |       -197.406 |            1.112 |          15 |         0.910 |       3808.731 |       -1237.858 | [0.26533414864616645, 2.343396174338847]    | RT_R_deceleration | primary  | rt          |
| 654 |      0.220 |       -0.110 |    48.624 |   40694.606 |    1.204 |     1.138 |      -8.465 |  -21429.777 |          1 |       33 |         0.134 |      10005.259 |            0.120 |         651 |         0.131 |      26602.656 |       -6082.760 | [-0.03466584988254052, 0.49888263271468136] | PT_unconditional  | primary  | pt          |
| 654 |     -0.602 |       -0.285 |    45.413 | -133261.930 |    0.598 |     0.653 |     -12.333 | -136408.699 |          1 |       33 |        -0.665 |    -159670.706 |           -0.703 |         651 |        -0.514 |    -118741.020 |       -7030.109 | [-0.8806597953455312, -0.35202576988980533] | RT_unconditional  | primary  | rt          |

## Matched execution (identical dates)

| name              |   n |   excluded |   open_mean |   open_cash |   delayed_mean |   delayed_cash |
|:------------------|----:|-----------:|------------:|------------:|---------------:|---------------:|
| PT_U1             |  24 |          1 |       1.956 |   25003.746 |          1.199 |      17809.335 |
| PT_R1             |  14 |          0 |       2.312 |   10655.045 |          2.211 |      11135.434 |
| PT_D1             |  20 |          0 |       0.762 |    3860.810 |         -0.059 |       -701.873 |
| PT_C1             |  13 |          0 |       1.667 |    5879.423 |          0.988 |       2157.087 |
| PT_PT_matrix      |  71 |          1 |       1.637 |   45399.025 |          1.006 |      30399.983 |
| RT_UR_volume      |  23 |          0 |       0.811 |    8706.204 |          1.016 |      10703.938 |
| RT_R_deceleration |  15 |          0 |       1.211 |    5177.304 |          0.910 |       3808.731 |

## Screening funnel

{
  "n30": 239,
  "n30_positive": 20,
  "n30_mean_ge03": 5,
  "n30_positive_delete5_mean": 0,
  "n30_positive_all3years": 0,
  "available_factors": 38
}

## CLV / 3day CLV / volume quintiles, ALL, RT net

| factor       | stage   |   bucket |   n |   mean_pct |   median_pct |   win_pct |       cash |   pf_pct |   pf_cash |   worst_pct |   mdd_cash |   clusters |
|:-------------|:--------|---------:|----:|-----------:|-------------:|----------:|-----------:|---------:|----------:|------------:|-----------:|-----------:|
| volume_ratio | ALL     |        1 | 127 |     -0.730 |       -0.678 |    33.858 | -36067.657 |    0.476 |     0.496 |      -9.705 | -37799.079 |         31 |
| volume_ratio | ALL     |        2 | 126 |     -0.495 |       -0.081 |    49.206 | -19670.921 |    0.641 |     0.710 |     -11.125 | -32133.765 |         41 |
| volume_ratio | ALL     |        3 | 132 |     -0.567 |       -0.061 |    49.242 | -28062.874 |    0.603 |     0.652 |     -10.701 | -33268.680 |         36 |
| volume_ratio | ALL     |        4 | 145 |     -1.128 |       -0.880 |    40.000 | -52339.317 |    0.433 |     0.524 |     -11.915 | -53366.773 |         34 |
| volume_ratio | ALL     |        5 | 124 |     -0.004 |        0.302 |    55.645 |   2878.839 |    0.997 |     1.053 |     -12.333 | -15392.723 |         30 |
| clv          | ALL     |        1 | 135 |     -0.916 |       -0.721 |    37.037 | -46734.915 |    0.358 |     0.381 |     -12.229 | -46895.317 |         42 |
| clv          | ALL     |        2 | 114 |     -1.019 |       -0.840 |    36.842 | -43581.484 |    0.427 |     0.446 |     -10.106 | -44449.178 |         43 |
| clv          | ALL     |        3 | 131 |     -0.589 |       -0.099 |    48.855 | -29344.773 |    0.595 |     0.625 |     -10.701 | -38813.050 |         40 |
| clv          | ALL     |        4 | 132 |     -0.310 |       -0.011 |    49.242 |   1230.491 |    0.791 |     1.018 |     -12.333 | -22056.824 |         41 |
| clv          | ALL     |        5 | 142 |     -0.254 |        0.518 |    53.521 | -14831.249 |    0.818 |     0.819 |     -11.915 | -23517.136 |         43 |
| clv3         | ALL     |        1 | 111 |     -0.891 |       -0.639 |    37.838 | -39409.329 |    0.434 |     0.428 |     -12.229 | -40582.108 |         40 |
| clv3         | ALL     |        2 | 134 |     -0.968 |       -0.745 |    41.791 | -48396.921 |    0.381 |     0.416 |     -12.333 | -48887.262 |         39 |
| clv3         | ALL     |        3 | 126 |     -0.599 |       -0.535 |    40.476 | -10072.230 |    0.607 |     0.855 |      -9.916 | -36489.893 |         42 |
| clv3         | ALL     |        4 | 144 |     -0.565 |       -0.152 |    48.611 | -39414.237 |    0.630 |     0.570 |     -11.915 | -42175.286 |         37 |
| clv3         | ALL     |        5 | 139 |     -0.062 |        0.516 |    56.115 |   4030.787 |    0.953 |     1.057 |     -10.155 | -20442.875 |         44 |

## Retrospective walk-forward

| direction   |   year | selected               |   train_mean |   n |   mean_pct |   median_pct |   win_pct |      cash |   pf_pct |   pf_cash |   worst_pct |   mdd_cash |   clusters |
|:------------|-------:|:-----------------------|-------------:|----:|-----------:|-------------:|----------:|----------:|---------:|----------:|------------:|-----------:|-----------:|
| rt          |   2024 | C__drawdown60__low     |        0.421 |   0 |    nan     |      nan     |   nan     |     0.000 |  nan     |   nan     |     nan     |      0.000 |          0 |
| rt          |   2025 | C__drawdown60__low     |        0.421 |   4 |     -2.459 |       -2.694 |    25.000 | -6202.618 |    0.167 |     0.159 |      -6.417 |  -6202.618 |          1 |
| rt          |   2026 | C__clv__high           |        0.272 |  12 |     -0.339 |        0.755 |    58.333 | -2436.938 |    0.762 |     0.770 |      -9.500 |  -8652.369 |          6 |
| pt          |   2024 | U__beta_residual1__low |        0.767 |  14 |      0.087 |       -0.225 |    42.857 |    56.352 |    1.131 |     1.024 |      -4.846 |  -1383.831 |          6 |
| pt          |   2025 | U__overnight5__high    |        0.670 |  31 |      0.700 |       -0.413 |    41.935 |  9308.229 |    1.551 |     1.436 |      -7.803 |  -8253.680 |          5 |
| pt          |   2026 | U__bias5__low          |        1.251 |   3 |     -0.004 |       -0.039 |    33.333 |    26.182 |    0.975 |     1.077 |      -0.495 |   -337.936 |          2 |

## Common cash benchmark

| name                          |   initial_common_cash |   cash_increment |   incremental_return_on_initial_stock_plus_cash_pct |   skipped |   T_cash_mdd | boundary                                                                             |
|:------------------------------|----------------------:|-----------------:|----------------------------------------------------:|----------:|-------------:|:-------------------------------------------------------------------------------------|
| PT_PT_matrix                  |             80051.638 |        45428.671 |                                              47.794 |         0 |    -3574.829 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_UR_volume                  |             80051.638 |         8706.204 |                                               9.159 |         0 |    -1769.245 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_R_deceleration             |             80051.638 |         5177.304 |                                               5.447 |         0 |    -1237.858 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| PT_unconditional              |             80051.638 |        40694.606 |                                              42.813 |         0 |   -21429.777 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_unconditional              |             80051.638 |       -76434.917 |                                             -80.414 |        18 |   -81745.212 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_factor_C__clv__high        |             80051.638 |         4051.069 |                                               4.262 |         0 |    -8652.369 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_factor_C__amihud20__high   |             80051.638 |         5141.667 |                                               5.409 |         0 |    -3174.973 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |
| RT_factor_U__combo_exhaustion |             80051.638 |         9960.837 |                                              10.479 |         0 |    -7824.641 | ex-post sufficient reserve; stock/dividend baseline shared, not total account return |

## Limitations

After-open gap factors must use post-open proxy; US economic closes are time-aligned but FRED historic publication availability is not certified. No literal auction strategy promotion for either category.

Contemporaneous D and peak/trough labels use outcomes and are descriptive only. Linked returns across disjoint D days are attribution, not a contiguous stock/account return.

No qualified rule means not adopted in this tested scope; it does not prove every possible factor fails. Existing positive-T ratings are not certified by this direction-only comparison.