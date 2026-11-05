# Data provenance and evaluation notes

This project originated as a **fictional client brief for a university team assignment**. The provided datasets were limited and contained missing values and inconsistencies. The workflow combines exploratory analysis, conservative cleaning, model-based approximations and synthetic scenarios.

## What the results mean

A supplementary offline comparison reported test **RMSE 8.031°** and **R² 0.818** for a Ridge regression selected to approximate a modelled rotation-control policy. These figures assess agreement with a simulated/provisional target, **not accuracy against real panel angles or agricultural field observations**.

The principal project documentation describes an intermediate modelling dataset with **1,003 records and 17 variables**. Separately generated scenario datasets are different and cannot be treated as independent real-world ground truth.

## Before reusing or publishing datasets

- Confirm the course's and original providers' redistribution terms.
- Do not commit private source data, secrets, student information, or huge output exports.
- Keep synthetic examples explicitly labelled as synthetic.
- Re-run metrics from a documented train/test split before claiming reproducibility.
