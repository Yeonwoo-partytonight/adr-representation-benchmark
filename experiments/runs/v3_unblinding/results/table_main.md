| id | slot | label | status | delta_obs | ci_low | ci_high | ci_status | p_raw | p_adj_panel1 | p_adj_panel2 | decision | tost | base | treat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | ① | M2b − M1b (RF · primary) | confirmatory | -0.006324167855457974 | -0.01631979733530217 | 0.0005022188133184531 | estimable | 0.23347665233476653 |  |  | RQ2 = rq2_decision(원 p · 무보정) | Inconclusive | M1b | M2b |
| C2 | ② | M2b − P-ID | confirmatory | -0.01859785531900579 | -0.026589781855748833 | -0.012083831188583609 | estimable | 9.999000099990002e-05 | 0.0006999300069993001 | 0.0006999300069993001 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-ID | M2b |
| C3 | ③ | M2b − P-FAM | confirmatory | -0.008372529740464735 | -0.017724908775914715 | -0.0018306019568997038 | estimable | 0.057394260573942604 | 0.286971302869713 | 0.34436556344365565 | RQ3(판1 Holm 조정 p · H3) | Inconclusive | P-FAM | M2b |
| C4 | ④ | M2b vs 자연 임베딩 재배치 null | confirmatory |  |  |  |  | 0.965034965034965 | 0.9881011898810119 | 1.0 | RQ4 = rq4_decision(판1 조정 p, 판1 조정 p) · 원 p_emp 2개 별도 칸 |  |  |  |
| C5 | ⑤ | M2b − M0 | confirmatory | 0.005483205168877542 | -0.0046739007689148475 | 0.012896151203300987 | estimable | 0.32936706329367066 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | M0 | M2b |
| C6 | ⑥ | M2b − RF_tuned | confirmatory | 0.009210235944827366 | -0.0007722179906984651 | 0.016007018771262684 | estimable | 0.35766423357664234 | 0.9881011898810119 | 1.0 | Holm 표 | Inconclusive | RF_tuned | M2b |
| C7 | ⑦ | RF+seq − RF (ens − M0) | confirmatory | -0.0010989134151744018 | -0.0024749418684072893 | 0.0009684456419485055 | estimable | 0.23607639236076391 | 0.9443055694430557 | 1.0 | Holm 표 | Equivalent | M0(p_RF) | ens |
| C8 | ⑧ | RQ-int (Δ_RF vs Δ_GIN) | confirmatory |  |  |  |  | 0.00021999780002199978 | 0.0013199868001319986 | 1.0 | RQ-int = 판1 Holm 조정 p < α (D7 · H3) · 판2(⑧ = 1.0) 병기(D14) |  |  |  |
| C-CAP | RQ3d | M2b − C-CAP | secondary_decision | 0.023767005819215925 | 0.016013085435127514 | 0.028495763794111874 | estimable | 9.999000099990002e-05 |  |  | H2: _contrast_pass(ci_primary, 원 p) → 최소 성립 조건 (Holm family 밖 · 무보정) | Positive | C-CAP | M2b |
| S-RQ1 | RQ1 | M1 − M0 | secondary | 0.0029941851112579854 | 0.0010590294628741938 | 0.0050296383073101135 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Equivalent | M0 | M1 |
| S-RQ1b | RQ1b | M1b − M1 | secondary | 0.00881318791307753 | 0.006068651695134552 | 0.011504953578289026 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M1 | M1b |
| S-M2 | M2 | M2 − M1 | secondary | -0.0021303003340538418 | -0.012407213284871972 | 0.004805869236717105 | estimable | 0.718028197180282 |  |  | 비판정 | Inconclusive | M1 | M2 |
| S-7h | ⑦h | ens_half − M0 (λ = 0.5) | secondary | -0.03532509549041027 | -0.042938254051190276 | -0.02218127826197649 | estimable | 9.999000099990002e-05 |  |  | 비판정 | Inconclusive | M0(p_RF) | ens_half |
| S-7s | ⑦s | ens_sens − M0 | secondary | -0.0009985848730177382 | -0.0022822584706261887 | 0.000901750895516047 | estimable | 0.22497750224977503 |  |  | 비판정 | Equivalent | M0(p_RF) | ens_sens |
| S-pch | ①pch | M2b_pchembl − M1b_pchembl | sensitivity | -0.006757920983905041 | -0.016416919429555792 | -0.00028551247023092915 | estimable | 0.1628837116288371 |  |  | 비판정 · ① pChEMBL 민감도 | Inconclusive | M1b_pchembl | M2b_pchembl |
| S-fsc | ③fsc | M2b − P-FAM_selfclust | sensitivity | -0.016945839426196596 | -0.02542971049139943 | -0.010161419450953068 | estimable | 9.999000099990002e-05 |  |  | 비판정 · ③ family 정의 민감도 | Inconclusive | P-FAM_selfclust | M2b |
| S-unit-drug | ①unit | M2b − M1b bootstrap 단위 = drug | sensitivity | -0.006324167855457974 | -0.01335283873253267 | 7.259081595379845e-05 | estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
| S-unit-sw | ①unit | M2b − M1b bootstrap 단위 = size_weighted | sensitivity | -0.006324167855457974 |  |  | not_estimable |  |  |  | 비판정 · ci_primary 그대로(percentile 아님) |  | M1b | M2b |
