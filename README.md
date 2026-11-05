# Sol i Sòl — AI for Agrivoltaic Decision Support

**University team project · BSc in Artificial Intelligence · Universitat Politècnica de Catalunya (UPC) · 2026**

> **Academic simulation:** We worked from a fictional client's brief and limited, imperfect datasets. This is an educational prototype, not a deployed system or a real commercial engagement.

## The challenge

In agrivoltaic installations, adjusting solar-panel tilt involves trade-offs between electricity generation, available light for crops and mechanical constraints. Our project explored decision-support recommendations that balance these factors when the supplied data are sparse, incomplete and inconsistent.

## Project workstreams

- **Data preparation:** exploratory analysis, missing-value assessment, temporal data integration and feature engineering.
- **Multi-objective control:** recommendation of panel tilt with energy, agricultural and movement considerations.
- **Machine-learning modelling:** comparison of regression models to approximate a simulated rotation-control policy.
- **Scenario generation:** synthetic examples to explore conditions beyond the limited source data.
- **Decision-support dashboard:** visual representation of recommendations, alerts and scenario trade-offs.
- **Project management:** simulated client tender, budget, risk register, responsibilities and milestones.

## Results — with context

A supplementary offline comparison reported a selected **Ridge regression** model with **test RMSE 8.031°** and **R² 0.818**. These figures reflect **agreement with a simulated/provisional target**, *not* accuracy validated in an agricultural installation.

A separate preprocessing/modelling phase described **1,003 records and 17 variables**. Generated synthetic datasets are not independent real-world ground truth.

## What is currently available in this repository

- `scripts/export_control_policy.py`: an original Python script that exports a recommendation as a machine-readable JSON policy; it does **not** actuate machinery.
- `examples/dashboard_data.sample.json`: a tiny, explicitly **synthetic** input example.
- `tests/test_control_policy.py`: a repeatable smoke test for JSON export.
- `docs/RUNNING_THE_CODE.md`: commands for the runnable sample.
- `docs/DATA_AND_EVALUATION.md`: provenance and interpretation of reported metrics.
- `docs/PROJECT_SCOPE.md`: scope and limitations.

**The complete controller, training scripts, dashboard and original datasets are not yet published in this branch.** They are being curated for permissions, dependencies and reproducibility.

## Quick start (synthetic example)

```bash
python -m pip install -r requirements.txt
python scripts/export_control_policy.py --dashboard-data examples/dashboard_data.sample.json --comparison examples/nonexistent.csv --crop tomato --panel semi_transparent --out outputs/sample_policy.json
python -m unittest discover -s tests -v
```

See [running instructions](docs/RUNNING_THE_CODE.md). No original dataset is needed for this small smoke test.

## Limitations

This is a university simulation using approximate physical/agronomic models and simulation-derived targets. Live hardware integration, measured photovoltaic production, measured crop yield and field validation were outside the prototype's scope.

## Credits

Developed collaboratively as a **university team project**. No individual contribution breakdown is needed for this project overview. Redistribution and contributor permissions should be checked before publishing the whole deliverable.
