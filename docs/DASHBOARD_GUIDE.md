# Original dashboard — guide to the coursework files

The original dashboard was submitted as a client-style demonstration. Its browser entry point is **`dashboard/index.html`** (HTML, not `index.md`).

## What it displays
The original dashboard README describes simulated sensor conditions, panel tilt recommendations, time series for energy and crop lighting, alerts and reasons for movements, crop cycles and a field designer comparing different crops and PV module types.

## Files in the submitted dashboard
- `dashboard/index.html` — HTML/CSS/JavaScript interface (about 323 KB).
- `dashboard/build_dashboard_data.py` — data generator using the model/controller scripts and source data.
- `dashboard/dashboard_data.json` — generated payload (about 107 MB, **omitted**).
- `dashboard/generar_autonom.py` — standalone HTML exporter.
- `dashboard/SOL_I_SOL_dashboard_autonom.html` — self-contained original demonstration (about 107 MB, **omitted**).
- `dashboard/README.md` — original dashboard instructions (in Catalan).

**These original dashboard source files are being prepared for addition and are not yet all present in this GitHub branch.** Do not interpret the available synthetic policy demo as the full dashboard.

## How to view the full version locally

After receiving the original permitted/generated `dashboard_data.json`, put it next to `index.html` and run:

```bash
python -m http.server 8501 --directory dashboard
```

Then open `http://localhost:8501`. Without its JSON payload, the original HTML does not show the full historical/simulated results.

The autonomous HTML from the course submission embeds the data in one large HTML file. GitHub ordinarily does **not** render HTML files as an interactive website from the code view; a proper static demo would require a hosted site with a size-controlled, rights-cleared data subset.

## Methodology
See [sources and methods](SOURCES_AND_METHODS.md) and the original university technical report for the details and bibliography. The ground irradiance computation is a parameterized approximation, **not a complete validated 3D ray-tracing simulation**.
