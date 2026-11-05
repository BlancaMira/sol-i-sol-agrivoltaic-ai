# Technical foundations and source provenance

This is a **summary of the team's technical report**, `Documentació - Sol i Sòl.pdf`, especially its data preparation, modelling, dashboard and bibliography sections. This page summarizes the cited sources; it does not independently validate their scientific claims or grant redistribution permission for the original materials.

## Data and preparation

The team's report documents an original dataset of **3,153 temporal observations**, with multiple sensor zones and extensive missingness. We investigated missing-value patterns, operational periods, timestamps and internal consistency. A conservative preprocessing strategy kept extended gaps unfilled and produced a modelling dataset of **1,003 records and 17 variables** for the documented phase. Those figures refer to the report's preprocessing workflow, not all datasets produced by the controller.

The dashboard-building script reads a meteorological file named `Viladecans - les Filipines - estacio.xls`; the original package also includes generated control and ground-scan CSVs. The source XLS and large generated outputs are **not included here pending review of redistribution rights**.

## Physical and agronomic decision-support model

The controller combines a simplified solar/energy component, a crop-light and environmental comfort proxy, and a movement penalty. It recommends a candidate panel angle using multi-objective scoring, subject to control rules. The display is a **model-based educational prototype**, not a real-time validated control system.

The dashboard's panel types are represented by transparency settings of **10%, 40%, and 60%**, with small configured bifacial gains. Crops explored include lettuce, tomato, fava beans and onions.

The team's report explicitly states that the crop/ground irradiance modelling relies on a parametric, auditable ground scan rather than a complete 3D RADIANCE scene. Descriptive labels or graphics should not be mistaken for measured ground irradiance.

## Supervised modelling

The model-training stage aims to **approximate the rotation policy produced by the controller**. Reported offline evaluation of a selected Ridge Regression model includes test **RMSE 8.031°** and **R² 0.818**. The target is model-generated; these metrics must not be represented as field-observed rotation accuracy or proven energy/crop improvements.

## Dashboard

The original UI lives in `dashboard/index.html`. It reads a generated `dashboard/dashboard_data.json`; the source builder is `dashboard/build_dashboard_data.py`. The original autonomous export `SOL_I_SOL_dashboard_autonom.html` embeds this very large JSON and is **not suitable for an ordinary GitHub repository** (over 100 MB in the provided archive). The HTML entry point alone is insufficient to display the complete original time series.

## Selected references from the submitted report

**Meteorological data**
- [Servei Meteorològic de Catalunya — Open data](https://www.meteo.cat/wpweb/serveis/cataleg-de-serveis/serveis-oberts/dades-obertes/)
- [Meteocat — XEMA observations](https://www.meteo.cat/observacions/xema)
- [Meteocat API documentation](https://apidocs.meteocat.gencat.cat/documentacio/)
- [RuralCat — agrometeorological data](https://ruralcat.gencat.cat/web/guest/agrometeo.estacions)

**Solar geometry, tracking and agrivoltaics**
- [pvlib Python documentation](https://pvlib-python.readthedocs.io/)
- [pvlib — single-axis tracking example](https://pvlib-python.readthedocs.io/en/stable/gallery/solar-tracking/plot_single_axis_tracking.html)
- [pvlib — agrivoltaics ground irradiance](https://pvlib-python.readthedocs.io/en/stable/gallery/agrivoltaics/plot_agrivoltaics_ground_irradiance.html)
- [Sandia PVPMC — single-axis tracking](https://pvpmc.sandia.gov/modeling-guide/1-weather-design-inputs/array-orientation/single-axis-tracking/)
- [NREL — bifacial irradiance and performance modelling](https://www.nrel.gov/pv/pv-bifacial-irradiance-toolkit)
- [Robledo et al. — Agrivoltaic greenhouse bifacial PV simulation parameters](https://doi.org/10.13140/RG.2.2.18672.74245)

**Agronomic context**
- [FAO — Onion crop information](https://www.fao.org/land-water/databases-and-software/crop-information/onion/en/)
- [Agriculture Victoria — Faba bean guidance](https://agriculture.vic.gov.au/crops-and-horticulture/grains-pulses-and-cereals/growing-grains-pulses-and-cereals/growing-faba-bean-in-victoria)
- [Gavhane et al. — Lettuce daily light integral](https://pmc.ncbi.nlm.nih.gov/articles/PMC10322904/)

The full university report contains **additional references and context**. Source links are credited to their respective authors and publishers; third-party reference PDFs are intentionally excluded from the repository.
