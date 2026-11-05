# DSS - Comparació model biològic/físic vs model data-driven

Aquest informe converteix el treball existent en una peça explícita de DSS per a licitació.
El model biològic/físic és el controlador multiobjectiu aplicat al dataset de candidats; el model data-driven és el millor model exportat.

## Resultats globals

- Files comparades: 34460
- Model data-driven: `outputs/rotation_model_selection_robust_raytrace/best_rotation_model.json`
- Diferència absoluta mitjana: 4.56 graus
- Coincidència ±5 graus: 72.4%
- Coincidència ±10 graus: 85.8%

## Bandes de coincidència

- match_0_5deg: 24937
- near_5_10deg: 4619
- disagreement_10_20deg: 3809
- strong_disagreement_gt20deg: 1087
- nan: 8

## Principales razones de desacuerdo

- match_within_5deg: 24937
- minor_difference_5_10deg: 4619
- controller_deviates_from_solar_tracker_for_multiobjective_tradeoff: 2185
- ml_controller_policy_disagreement: 1913
- controller_prioritizes_crop_stress: 794
- controller_prioritizes_wind_stow: 12

## Interpretación

Las filas con desacuerdo fuerte son candidatas para revisión agronómica o de control: pueden señalar situaciones donde el modelo aprendido suaviza o no replica restricciones explícitas del controlador, como estrés del cultivo, viento o desviación deliberada respecto al tracker solar puro.