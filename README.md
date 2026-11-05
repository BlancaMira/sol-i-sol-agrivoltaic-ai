# Sol i Sòl — AI for Agrivoltaic Decision Support

**Academic team project · BSc in Artificial Intelligence · Universitat Politècnica de Catalunya (UPC) · 2026**

> **Academic simulation:** We worked from a fictional client's brief and limited, imperfect datasets. This is an educational prototype, not a deployed system or a real commercial engagement.

## Problem
In agrivoltaic installations, adjusting solar-panel tilt involves trade-offs between electricity generation, light available to crops and mechanical/operational constraints. Our objective was to design a decision-support prototype that recommends a panel rotation based on those competing factors.

## What we developed
- **Data exploration and preparation:** investigate missing values, anomalies, timestamps and data quality; engineer modelling features.
- **Multi-objective controller:** compare candidate tilt angles under energy, agricultural and movement criteria.
- **Machine-learning evaluation:** train and compare regression approaches for approximating a simulated rotation-control policy.
- **Synthetic scenarios:** generate additional scenarios to investigate system behaviour beyond the limited supplied data.
- **Decision-support dashboard:** communicate recommended angles, trade-offs, alerts and scenario comparisons.
- **Project planning:** simulate a client proposal including scope, budget, risk assessment, responsibilities and milestones.

## Reported results and interpretation
One supplementary offline model comparison reports a selected **Ridge regression** model with **test RMSE 8.031°** and **R² 0.818**. These are metrics for approximating a **modelled/provisional rotation policy**, *not* field-validated accuracy of physical solar-panel tracking. Other phases use different datasets and evaluation setups.

The project documentation also reports a modelling phase with **1,003 records and 17 variables** after conservative preprocessing of the initial limited data. This number should not be confused with the size of synthetic scenario datasets.

## Technologies
Python, data cleaning and feature engineering, regression, model evaluation, optimization and dashboard development.

## Reproducibility
The original university submission includes scripts, a dashboard and output datasets. We are curating the source code and reproducibility instructions before publishing a reusable release. Original third-party inputs, large generated outputs and redistribution-restricted files are intentionally excluded.

## Limitations
The controller and agricultural/energy calculations use approximations and simulations. We did not validate the system with a live solar installation, hardware actuators or field experiments.

## Credits
Developed as a **university team project**. Individual contributions are not broken down in this overview. Please check contributor and redistribution permissions before reusing the complete coursework deliverable.
