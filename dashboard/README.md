# Sol i Sòl — interactive dashboard

**Open `index.html` directly in Chrome, Firefox, or Edge.** This version embeds a representative 7-day subset of the university project simulation, so it works **without a local server or a separate JSON request**.

The interface and control logic are preserved from the original submission. Select a crop, panel type and date to explore the recommendation, visualizations, energy/crop metrics and alerts.

## Files

- `index.html` — **standalone portfolio dashboard** (the one to open with double click).
- `index.server.html` — unmodified original interface, loads `dashboard_data.json` via HTTP.
- `dashboard_data.json` — reduced generated dataset extracted from the original coursework outputs; not field observations.
- `build_dashboard_data.py` — original data-building script, requires data dependencies omitted from the portfolio.
- `generar_autonom.py` — original standalone exporter (embeds the entire JSON into an HTML file).

## Optional server-based version

From the project root:

```bash
python -m http.server 8501 --directory dashboard
```

Then open `http://localhost:8501/index.server.html`. Opening the server version via `file://` may show empty dropdowns because browsers block `fetch()` of local JSON files.

## Limitations

The 7-day subset is a simulation-derived demonstration prepared for portfolio display; it is not the full original 100+ MB dataset. The agrivoltaic control decisions are modelled estimates and have not been field validated. For model and source provenance, see `docs/SOURCES_AND_METHODS.md`.
