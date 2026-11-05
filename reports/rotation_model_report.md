# Informe Sprint 2 - Model de prediccio de rotacio

## Target i dades

Target històric detectat: `best_angle_deg`.

## Models comparats

- Mitjana historica d'angle.
- Geometria solar simple.
- Referencia fisica del tracker amb biaix apres.
- Regressio Ridge amb diferents regularitzacions.
- KNN regressor amb diversos valors de k.
- Regles interpretables per franges d'hora, irradiancia i temperatura.

## Millor model

`ridge_regression`

## Metriques en test

- RMSE: 8.031 graus
- MAE: 4.675 graus
- R2: 0.818
- Accuracy ±5 graus: 73.7%
- Accuracy ±10 graus: 85.0%

## Ranking de validacio

| model | rmse | mae | r2 | acc_5deg | acc_10deg |
| --- | --- | --- | --- | --- | --- |
| ridge_regression | 7.1820 | 4.5777 | 0.8837 | 0.7225 | 0.8733 |
| ridge_regression | 7.3889 | 4.9623 | 0.8769 | 0.6912 | 0.8688 |
| ridge_regression | 7.5057 | 5.1451 | 0.8730 | 0.6633 | 0.8636 |
| ridge_regression | 7.5336 | 5.1835 | 0.8720 | 0.6589 | 0.8628 |
| knn_regressor | 9.5506 | 4.7465 | 0.7943 | 0.6987 | 0.8382 |
| knn_regressor | 9.9103 | 5.3104 | 0.7785 | 0.6803 | 0.8071 |
| knn_regressor | 10.9375 | 6.2170 | 0.7302 | 0.6349 | 0.7848 |
| tracker_reference_bias | 11.1620 | 4.9149 | 0.7190 | 0.7560 | 0.8514 |
| solar_geometry | 13.1638 | 7.9074 | 0.6092 | 0.8361 | 0.8663 |
| knn_regressor | 13.2727 | 7.2784 | 0.6027 | 0.6411 | 0.7672 |
| binned_rules | 13.6860 | 6.9234 | 0.5776 | 0.6790 | 0.8127 |
| mean_angle | 21.0643 | 11.3600 | -0.0006 | 0.6459 | 0.6769 |

## Features utilitzades

`ghi_wm2`, `dhi_wm2`, `dni_wm2`, `air_temp_c`, `soil_temp_c`, `relative_humidity_pct`, `wind_speed_ms`, `precipitation_mm`, `eto_mm`, `solar_elevation_deg`, `solar_azimuth_deg`, `cos_zenith`, `dli_reference_mol`, `hour_sin`, `hour_cos`, `doy_sin`, `doy_cos`, `month_sin`, `month_cos`, `previous_angle_deg`, `tracker_reference_angle_deg`, `crop_cycle_day`, `crop_cycle_progress`, `crop_days_to_planting`, `crop_cycle_days_expected`, `crop_stage_productive_num`, `crop_stage_penalty`, `module_transparency`, `pitch_m`, `gcr`, `albedo`, `crop_lettuce`, `crop_tomato`, `crop_fava`, `crop_onion`, `stage_establishment`, `stage_leaf_expansion`, `stage_harvest_window`, `stage_summer_offseason_heat_risk`, `stage_winter_offseason`, `stage_vegetative`, `stage_flowering_fruiting`, `stage_late_crop`, `stage_winter_vegetative`, `stage_flowering_pods`, `stage_initial_establishment`, `stage_vegetative_growth`, `stage_bulbing`, `stage_ripening_drydown`, `stage_late_summer_offseason`

## Limitacions i proxims passos

- Si el target es provisional, les metriques mesuren la capacitat d'imitar la politica optima generada, no un tracker real.
- Quan hi hagi angle historic real, executar amb `--target nom_columna_angle`.
- Per al dashboard, carregar el JSON del millor model o usar el CSV de prediccions generat.
- Si l'entrada es un dataset `hora x angle x cultiu` (`ground_scan_all_crops.csv` o antic `raytrace_all_crops.csv`), es col·lapsa primer a una fila per hora i cultiu amb `best_angle_deg`.