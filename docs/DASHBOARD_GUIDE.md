# Dashboard guide

The portfolio dashboard is available at **`dashboard/index.html`**. It is the original university interface exported as a self-contained HTML file, with a curated week of simulation results embedded inside. Download and open it directly in a browser; there is no separate JSON file to install.

## Available files

- `dashboard/index.html` — standalone, offline interactive dashboard (approximately 2.4 MB).
- `dashboard/index.server.html` — original interface before data embedding; requires its separately generated `dashboard_data.json`, which is **not included**.
- `dashboard/build_dashboard_data.py` — original data-building script (needs original input data).
- `dashboard/generar_autonom.py` — original self-contained export script.
- `dashboard/README.md` — practical instructions for the dashboard.

The portfolio sample contains one week of results generated for the coursework simulation, rather than the full original time series. **These are simulated results, not measurements from a working installation.**

## Viewing the demonstration

1. Download `dashboard/index.html` from GitHub.
2. Open the file in Chrome, Firefox or Edge.
3. Explore crops, panel configurations, dates and recommendations.

The `index.server.html` variant cannot run as a complete demonstration without the original external data file. Do not use it as the portfolio entry point.

For details about the controller, data preparation, performance claims and sources, see [sources and methods](SOURCES_AND_METHODS.md) and the [technical report](Sol_i_Sol_Technical_Report.pdf). Ground-irradiance modelling is a parameterized approximation, not validated 3D ray tracing.
