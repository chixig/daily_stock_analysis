# B16 final path and artifact verification

| scenario                            | first_quantity_change   |   terminal_cash_gap | unresolved_sale   |   unresolved_days |   sales2025 |   increment2025 |   calendar_event92_increment |   calendar_event92_sales | clock   |    full_cost |   available_cash |   cash_shortfall |   base_cash_surplus |   base_buy_quantity |   new_buy_quantity |
|:------------------------------------|:------------------------|--------------------:|:------------------|------------------:|------------:|----------------:|-----------------------------:|-------------------------:|:--------|-------------:|-----------------:|-----------------:|--------------------:|--------------------:|-------------------:|
| S1_F1_open_b5_e1_d0_extra_cost      |                         |            0.000000 |                   |                 0 |          46 |    10147.247125 |                  8776.962395 |                        7 | nan     |   nan        |       nan        |       nan        |          nan        |          nan        |         nan        |
| S1_F1_open_b5_e2_d0_extra_cost      |                         |            0.000000 |                   |                 0 |          46 |     9807.258671 |                  8678.459413 |                        7 | nan     |   nan        |       nan        |       nan        |          nan        |          nan        |         nan        |
| S1_F1_open_b10_e1_d0_extra_cost     | 2024-01-22              |         3261.797780 | 2025-04-22        |               340 |           2 |    -4242.588703 |                   266.000000 |                        0 | 09:25   | 14731.328262 |     14554.198199 |       177.130063 |          279.330516 |         1000.000000 |         900.000000 |
| S1_F1_open_b10_e2_d0_extra_cost     | 2023-12-12              |         3507.438629 | 2024-01-19        |               640 |           0 |    -4066.800000 |                   266.000000 |                        0 | 09:25   | 15633.888287 |     15602.318385 |        31.569902 |          864.621415 |         1000.000000 |         900.000000 |
| S1_F1_post0935_b5_e1_d0_extra_cost  |                         |            0.000000 |                   |                 0 |          46 |     8005.651782 |                 11118.706836 |                        7 | nan     |   nan        |       nan        |       nan        |          nan        |          nan        |         nan        |
| S1_F1_post0935_b5_e2_d0_extra_cost  |                         |            0.000000 |                   |                 0 |          46 |     7665.449297 |                 11020.437888 |                        7 | nan     |   nan        |       nan        |       nan        |          nan        |          nan        |         nan        |
| S1_F1_post0935_b10_e1_d0_extra_cost | 2023-04-06              |         3386.136227 | 2025-04-22        |               340 |           2 |    -4073.401111 |                   266.000000 |                        0 | 09:40   | 17754.680495 |     17636.826602 |       117.853893 |          267.847070 |         1000.000000 |         900.000000 |
| S1_F1_post0935_b10_e2_d0_extra_cost | 2023-03-24              |         3403.198345 | 2025-04-22        |               340 |           2 |    -4080.530024 |                   266.000000 |                        0 | 09:40   | 17155.727506 |     17041.056939 |       114.670566 |          635.801812 |         1000.000000 |         900.000000 |

## Complete nine-event cash entitlement

| scenario                      | event      | source_status   |   entitlement |   quantity | payment_date        | account_window                |
|:------------------------------|:-----------|:----------------|--------------:|-----------:|:--------------------|:------------------------------|
| S1_F1_open_b5_e0_d0_main      | 2019-06-20 | primary_new     |             0 |          0 | NaT                 | before_start_no_initial_claim |
| S1_F1_open_b5_e0_d0_main      | 2020-06-30 | primary_new     |             0 |          0 | 2020-06-30 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2021-07-27 | primary_new     |           250 |       1000 | 2021-07-27 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2022-08-05 | primary_new     |           500 |       1000 | 2022-08-05 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2023-07-28 | primary_new     |           550 |       1000 | 2023-07-28 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2024-08-15 | primary_new     |           580 |       1000 | 2024-08-15 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2025-07-31 | primary_reused  |           640 |       1000 | 2025-07-31 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2026-01-16 | primary_reused  |           330 |       1000 | 2026-01-16 00:00:00 | included                      |
| S1_F1_open_b5_e0_d0_main      | 2026-08-03 | primary_new     |           650 |       1000 | 2026-08-03 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2019-06-20 | primary_new     |             0 |          0 | NaT                 | before_start_no_initial_claim |
| S1_F1_open_b10_e0_d0_main     | 2020-06-30 | primary_new     |             0 |          0 | 2020-06-30 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2021-07-27 | primary_new     |           250 |       1000 | 2021-07-27 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2022-08-05 | primary_new     |           500 |       1000 | 2022-08-05 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2023-07-28 | primary_new     |           550 |       1000 | 2023-07-28 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2024-08-15 | primary_new     |           580 |       1000 | 2024-08-15 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2025-07-31 | primary_reused  |           640 |       1000 | 2025-07-31 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2026-01-16 | primary_reused  |           330 |       1000 | 2026-01-16 00:00:00 | included                      |
| S1_F1_open_b10_e0_d0_main     | 2026-08-03 | primary_new     |           650 |       1000 | 2026-08-03 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2019-06-20 | primary_new     |             0 |          0 | NaT                 | before_start_no_initial_claim |
| S1_F1_post0935_b5_e0_d0_main  | 2020-06-30 | primary_new     |             0 |          0 | 2020-06-30 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2021-07-27 | primary_new     |           250 |       1000 | 2021-07-27 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2022-08-05 | primary_new     |           500 |       1000 | 2022-08-05 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2023-07-28 | primary_new     |           550 |       1000 | 2023-07-28 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2024-08-15 | primary_new     |           580 |       1000 | 2024-08-15 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2025-07-31 | primary_reused  |           640 |       1000 | 2025-07-31 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2026-01-16 | primary_reused  |           330 |       1000 | 2026-01-16 00:00:00 | included                      |
| S1_F1_post0935_b5_e0_d0_main  | 2026-08-03 | primary_new     |           650 |       1000 | 2026-08-03 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2019-06-20 | primary_new     |             0 |          0 | NaT                 | before_start_no_initial_claim |
| S1_F1_post0935_b10_e0_d0_main | 2020-06-30 | primary_new     |             0 |          0 | 2020-06-30 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2021-07-27 | primary_new     |           250 |       1000 | 2021-07-27 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2022-08-05 | primary_new     |           500 |       1000 | 2022-08-05 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2023-07-28 | primary_new     |           550 |       1000 | 2023-07-28 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2024-08-15 | primary_new     |           580 |       1000 | 2024-08-15 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2025-07-31 | primary_reused  |           640 |       1000 | 2025-07-31 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2026-01-16 | primary_reused  |           330 |       1000 | 2026-01-16 00:00:00 | included                      |
| S1_F1_post0935_b10_e0_d0_main | 2026-08-03 | primary_new     |           650 |       1000 | 2026-08-03 00:00:00 | included                      |

{
  "status": "PASS",
  "accounts_checked": 44,
  "original_files_unchanged": 627,
  "main_code_sha": "c8c97772b40cce15c755ba3345554d7ecf1cb7e4",
  "main_run_id": "35730079970",
  "original_manifest_sha256": "55de07314176bf8b5f41322b5680b884f634f23d39aed92a7837180e1e615b8d",
  "expected_live_log_difference": [
    "research/foxconn_t0_20260922_b16/calculation.log"
  ],
  "source_primary_verified": 9,
  "corrected_price_version": false,
  "correction_reason": "cross-source discrepancy unresolved; no unsupported replacement",
  "finite_account_funding_explained": true,
  "verification_run_id": "35730482162",
  "verification_code_sha": "389d966b3d621c41a62f0b453dd400abf00c243e"
}