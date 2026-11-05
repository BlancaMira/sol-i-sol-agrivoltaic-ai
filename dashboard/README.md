# Sol i Sòl — interactive dashboard

**Open `index.html` directly in Chrome, Firefox or Edge.** This file embeds a representative seven-day subset of the university simulation and runs without an external JSON request or local web server.

Select a crop, panel type and date to explore the recommended angles, visualizations, energy/crop indicators and alerts.

## Files

- `index.html` — standalone HTML dashboard with embedded simulation data (recommended).
- `index.server.html` — original interface that requests a separate JSON file over HTTP.
- `build_dashboard_data.py` — original builder; requires original data sources omitted from the repository.
- `generar_autonom.py` — original exporter for an HTML file containing the simulation data.

The external `dashboard_data.json` from the original submission is **not included**. The standalone `index.html` already contains the reduced demonstration data.

## Scope

The subset represents one week of generated results, not the complete simulation or measured field observations. The modelled control decisions have not been validated against an operational installation.

For methods and data provenance, see [sources and methods](../docs/SOURCES_AND_METHODS.md).
