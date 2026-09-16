# B09 Intraday paths and overnight follow-through

All signals at14:50; primary buy close,sell next open. No adaptive threshold tuning.

| id                    | window       |    n |    mean |     win |         cash |   delete5 |   ci_low |   ci_high |   increment |
|:----------------------|:-------------|-----:|--------:|--------:|-------------:|----------:|---------:|----------:|------------:|
| ON0_common            | main2020     | 1623 | -0.3291 | 30.8071 | -132251.4706 |   -0.3543 |  -0.3979 |   -0.2636 |      0.0000 |
| ON0_common            | old2020_2023 |  970 | -0.3478 | 26.8041 |  -49881.0425 |   -0.3792 |  -0.4190 |   -0.2819 |      0.0000 |
| ON0_common            | recent2024   |  653 | -0.3014 | 36.7534 |  -82370.4281 |   -0.3611 |  -0.4248 |   -0.1572 |      0.0000 |
| L1_tail_up            | main2020     |  708 | -0.3869 | 28.9548 |  -79753.4980 |   -0.4326 |  -0.4714 |   -0.3035 |     -0.0578 |
| L1_tail_up            | old2020_2023 |  432 | -0.3825 | 25.0000 |  -25747.9652 |   -0.4216 |  -0.4789 |   -0.2965 |     -0.0347 |
| L1_tail_up            | recent2024   |  276 | -0.3938 | 35.1449 |  -54005.5328 |   -0.5125 |  -0.5470 |   -0.2380 |     -0.0924 |
| L2_tail_down          | main2020     |  815 | -0.2978 | 32.0245 |  -53867.4592 |   -0.3434 |  -0.3903 |   -0.1983 |      0.0313 |
| L2_tail_down          | old2020_2023 |  470 | -0.3283 | 28.0851 |  -21923.6059 |   -0.3886 |  -0.4274 |   -0.2355 |      0.0195 |
| L2_tail_down          | recent2024   |  345 | -0.2564 | 37.3913 |  -31943.8534 |   -0.3585 |  -0.4431 |   -0.0604 |      0.0451 |
| L3_afternoon_recovery | main2020     |  337 | -0.3855 | 28.4866 |  -31668.6614 |   -0.4571 |  -0.5157 |   -0.2408 |     -0.0564 |
| L3_afternoon_recovery | old2020_2023 |  216 | -0.4005 | 23.1481 |  -11771.6102 |   -0.4826 |  -0.5238 |   -0.2526 |     -0.0527 |
| L3_afternoon_recovery | recent2024   |  121 | -0.3588 | 38.0165 |  -19897.0512 |   -0.5427 |  -0.6642 |   -0.0523 |     -0.0574 |
| L4_afternoon_reversal | main2020     |  415 | -0.2783 | 29.8795 |  -24905.5175 |   -0.3508 |  -0.4139 |   -0.1518 |      0.0509 |
| L4_afternoon_reversal | old2020_2023 |  239 | -0.3256 | 23.8494 |  -11637.1123 |   -0.3964 |  -0.4479 |   -0.2119 |      0.0222 |
| L4_afternoon_reversal | recent2024   |  176 | -0.2140 | 38.0682 |  -13268.4052 |   -0.3861 |  -0.4884 |    0.0503 |      0.0874 |
| L5_breakout           | main2020     |   97 | -0.4816 | 25.7732 |  -14958.6097 |   -0.6856 |  -0.7888 |   -0.1503 |     -0.1524 |
| L5_breakout           | old2020_2023 |   55 | -0.5275 | 21.8182 |   -4540.7571 |   -0.6568 |  -0.7619 |   -0.2942 |     -0.1797 |
| L5_breakout           | recent2024   |   42 | -0.4215 | 30.9524 |  -10417.8526 |   -0.9207 |  -0.9852 |    0.3341 |     -0.1201 |
| L6_breakdown          | main2020     |  181 | -0.5156 | 30.9392 |  -23532.8261 |   -0.5919 |  -0.7437 |   -0.3012 |     -0.1865 |
| L6_breakdown          | old2020_2023 |  104 | -0.3851 | 29.8077 |   -5695.6713 |   -0.4781 |  -0.6596 |   -0.1800 |     -0.0373 |
| L6_breakdown          | recent2024   |   77 | -0.6920 | 32.4675 |  -17837.1548 |   -0.8904 |  -1.1807 |   -0.2949 |     -0.3905 |
| L7_tail_up_volume     | main2020     |  106 | -0.3225 | 28.3019 |  -14364.3766 |   -0.5624 |  -0.6248 |    0.0198 |     -0.0016 |
| L7_tail_up_volume     | old2020_2023 |   63 | -0.3706 | 26.9841 |   -3492.1237 |   -0.5388 |  -0.6048 |   -0.1641 |     -0.0362 |
| L7_tail_up_volume     | recent2024   |   43 | -0.2522 | 30.2326 |  -10872.2529 |   -0.8542 |  -0.9183 |    0.6013 |      0.0493 |
| L8_tail_down_volume   | main2020     |  106 | -0.4966 | 28.3019 |  -13003.2075 |   -0.7227 |  -0.9161 |   -0.1021 |     -0.1757 |
| L8_tail_down_volume   | old2020_2023 |   66 | -0.3316 | 27.2727 |   -3268.3343 |   -0.4538 |  -0.5204 |   -0.1489 |      0.0027 |
| L8_tail_down_volume   | recent2024   |   40 | -0.7689 | 30.0000 |   -9734.8732 |   -1.4601 |  -1.8702 |    0.2070 |     -0.4674 |

## Path decomposition

| id                    | window       |    n |   late_log_mean |   overnight_log_mean |   combined_log_mean |   late_price_mean |
|:----------------------|:-------------|-----:|----------------:|---------------------:|--------------------:|------------------:|
| ON0_common            | main2020     | 1623 |          0.0508 |              -0.0988 |             -0.0480 |            0.0512 |
| ON0_common            | old2020_2023 |  970 |          0.0525 |              -0.0775 |             -0.0250 |            0.0528 |
| ON0_common            | recent2024   |  653 |          0.0484 |              -0.1305 |             -0.0821 |            0.0489 |
| L1_tail_up            | main2020     |  708 |          0.0443 |              -0.1537 |             -0.1094 |            0.0446 |
| L1_tail_up            | old2020_2023 |  432 |          0.0382 |              -0.1102 |             -0.0720 |            0.0386 |
| L1_tail_up            | recent2024   |  276 |          0.0538 |              -0.2218 |             -0.1680 |            0.0541 |
| L2_tail_down          | main2020     |  815 |          0.0611 |              -0.0705 |             -0.0094 |            0.0616 |
| L2_tail_down          | old2020_2023 |  470 |          0.0721 |              -0.0592 |              0.0130 |            0.0725 |
| L2_tail_down          | recent2024   |  345 |          0.0461 |              -0.0861 |             -0.0399 |            0.0467 |
| L3_afternoon_recovery | main2020     |  337 |          0.0661 |              -0.1493 |             -0.0832 |            0.0665 |
| L3_afternoon_recovery | old2020_2023 |  216 |          0.0646 |              -0.1282 |             -0.0637 |            0.0650 |
| L3_afternoon_recovery | recent2024   |  121 |          0.0688 |              -0.1869 |             -0.1182 |            0.0692 |
| L4_afternoon_reversal | main2020     |  415 |          0.0553 |              -0.0475 |              0.0078 |            0.0558 |
| L4_afternoon_reversal | old2020_2023 |  239 |          0.0392 |              -0.0524 |             -0.0132 |            0.0395 |
| L4_afternoon_reversal | recent2024   |  176 |          0.0773 |              -0.0409 |              0.0363 |            0.0779 |
| L5_breakout           | main2020     |   97 |         -0.0113 |              -0.2536 |             -0.2649 |           -0.0108 |
| L5_breakout           | old2020_2023 |   55 |         -0.0446 |              -0.2500 |             -0.2946 |           -0.0439 |
| L5_breakout           | recent2024   |   42 |          0.0323 |              -0.2582 |             -0.2259 |            0.0326 |
| L6_breakdown          | main2020     |  181 |          0.0339 |              -0.2883 |             -0.2544 |            0.0345 |
| L6_breakdown          | old2020_2023 |  104 |          0.0519 |              -0.1157 |             -0.0638 |            0.0524 |
| L6_breakdown          | recent2024   |   77 |          0.0096 |              -0.5214 |             -0.5118 |            0.0104 |
| L7_tail_up_volume     | main2020     |  106 |         -0.0001 |              -0.0933 |             -0.0933 |            0.0006 |
| L7_tail_up_volume     | old2020_2023 |   63 |         -0.0253 |              -0.0977 |             -0.1230 |           -0.0246 |
| L7_tail_up_volume     | recent2024   |   43 |          0.0368 |              -0.0867 |             -0.0499 |            0.0374 |
| L8_tail_down_volume   | main2020     |  106 |          0.0485 |              -0.2683 |             -0.2198 |            0.0492 |
| L8_tail_down_volume   | old2020_2023 |   66 |          0.0705 |              -0.0509 |              0.0196 |            0.0711 |
| L8_tail_down_volume   | recent2024   |   40 |          0.0122 |              -0.6271 |             -0.6148 |            0.0131 |

## Gates

| id                    | passed   |   holm_mean |   holm_increment | execution_certified   |
|:----------------------|:---------|------------:|-----------------:|:----------------------|
| L1_tail_up            | False    |           1 |                1 | False                 |
| L2_tail_down          | False    |           1 |                1 | False                 |
| L3_afternoon_recovery | False    |           1 |                1 | False                 |
| L4_afternoon_reversal | False    |           1 |                1 | False                 |
| L5_breakout           | False    |           1 |                1 | False                 |
| L6_breakdown          | False    |           1 |                1 | False                 |
| L7_tail_up_volume     | False    |           1 |                1 | False                 |
| L8_tail_down_volume   | False    |           1 |                1 | False                 |

## Annual selection

|   year | id   |   n |
|-------:|:-----|----:|
|   2022 | NONE |   0 |
|   2023 | NONE |   0 |
|   2024 | NONE |   0 |
|   2025 | NONE |   0 |
|   2026 | NONE |   0 |

## Audit

{
  "data_end": "2026-09-11",
  "minute_days": 1624,
  "signal_dates": 1624,
  "valid_tail_volume": 1604,
  "input_hashes": {
    "research/foxconn_overnight_20260916_b08/daily_ledger.csv": "8d5ffd55d0a21e1ca2f76c19af81f1aefd0051c67c0fc9252607b82ce1ffce1c",
    "research/foxconn_overnight_20260916_b08/results.csv": "ad3bd3ddf290c5e6e4090af381a299be01432b99dce6be9fa0952812b3ea15c3",
    "research/foxconn_t0_20260913/results/daily_features_and_cashflows.csv": "336fd19b75d4489db11fbee4ac084744b6ea0c16802b3183bb128c43fd547e85",
    "research/foxconn_t0_20260913/source/601138-full-5min-history.zip": "6decd5fbe5916d974d7897f9259de6dbe0c319722bd3972a85d780cf25c1c5ff",
    "research/foxconn_t0_20260913_b02/source/sse_index.csv": "108cf1e67314f5c972ce064f39793368215a532ee701d6504a876a2c11d41c9c",
    "research/foxconn_t0_20260913/source/baostock_raw_crosscheck.csv": "52b880bacd8740ac79a4f7a31a8c21f2cb26e074d441797a44e9e3c8b6f97e10",
    "data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv": "78811cdfa3e493c3a65bb3d872e93fe3f66980f58673d7932c8e30e2b1d144d0",
    "research/foxconn_overnight_20260916_b08/features.csv": "5c318ba2ea0c9e2b4a9ac4c26bd5409169f2cab5d3a324469cde7a59af92c0e7"
  },
  "rule_count": 8,
  "passed": [],
  "checks": "B08 cash reproduction,source hashes,future-minute/daily-close mutation,prefix,coverage partition,log path identity,temporal training cutoff passed",
  "limitations": "Same previously explored history,not clean OOS. No auction queue certification,dividend vendor/settlement limitations inherited. Early-entry diagnostic is a different strategy,not automatic replacement. Frozen stages descriptive only."
}