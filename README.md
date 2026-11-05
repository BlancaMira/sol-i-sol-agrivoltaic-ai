# Sol i Sòl — Agrivoltaic Decision Support

**Artificial Intelligence degree · Universitat Politècnica de Catalunya (UPC) · 2026**

Sol i Sòl is a university team project developed in response to a fictional company's brief. The aim was to design a decision-support system for an agrivoltaic installation in Viladecans, where solar panels share space with crops.

Panel orientation affects both electricity generation and the light reaching the crops. We studied how a control system could balance these competing needs while accounting for weather conditions and limits on panel movement.

## The project

The initial datasets were limited and contained missing or inconsistent observations. A significant part of the work therefore involved assessing data quality, deciding how to handle incomplete records and documenting the assumptions needed to continue.

We then developed:
- A **data preparation workflow** to inspect, clean and combine the available measurements.
- A **multi-objective controller** to recommend panel angles using estimated photovoltaic performance, crop conditions and movement constraints.
- **Machine-learning models** trained to approximate the controller's rotation decisions, with comparisons between modelling approaches.
- **Synthetic scenarios** to explore situations not adequately represented in the supplied data.
- An **interactive dashboard** for exploring recommendations, crop conditions, energy indicators and different panel configurations.

Alongside the technical work, we prepared a project plan, budget, risk assessment and delivery proposal as we would for a real client. It was an academic simulation, not a commercial deployment.

## Dashboard

The dashboard was one of the main deliverables. It was built in HTML, CSS and JavaScript and allows users to explore several crops and photovoltaic panel types.

**[Open the dashboard file](dashboard/index.html)** after downloading it from the repository. This version contains a smaller selection of simulated results and opens locally without a server. The complete submission used a much larger dataset, which has been omitted to keep the repository manageable.

The example covers **15–21 July 2025**, with hourly records for four crops and three panel configurations. These are results from our simulation, not live sensor readings or measured agricultural outcomes.

## Technical approach

| Component | Description |
| --- | --- |
| Data preparation | Missing-value analysis, temporal alignment and feature engineering |
| Controller | Multi-objective scoring of candidate panel angles |
| Machine learning | Regression models for reproducing controller-generated decisions |
| Scenario generation | Synthetic environmental and operational situations |
| Dashboard | Visual analysis of recommendations and trade-offs |

The submitted report describes a preprocessing stage that reduced **3,153 time records** to **1,003 records with 17 modelling variables**. In one offline comparison, Ridge Regression achieved **R² = 0.818** and **RMSE = 8.031°** against a simulated rotation target. These metrics do **not** measure performance against real panel movements.

## Repository contents

- `dashboard/` — interactive interface and the scripts used to prepare its data.
- `scripts/` — controller, model training, scenario generation and comparison tools.
- `reports/` — selected model results and evaluation notes.
- `docs/` — technical report, methodology, assumptions and source references.
- `tests/` and `examples/` — small checks and illustrative inputs.

See [sources and methodology](docs/SOURCES_AND_METHODS.md) for the reference material behind the physical models, meteorological data and agronomic assumptions. The original technical report is written in Catalan.

## Scope and limitations

This was a proof of concept using simplified physical and agronomic models. We did not connect it to a real installation or validate energy production and crop yields in the field. Some results depend on synthetic data and model-generated targets.

## Team

Developed as a group project for the BSc in Artificial Intelligence at UPC.
