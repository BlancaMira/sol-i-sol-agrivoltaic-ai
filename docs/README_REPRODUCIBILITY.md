# Reproducibility note

The repository contains the original project scripts, a curated standalone dashboard and the technical report. The original large input datasets and full generated outputs are excluded.

## Dashboard

Download `dashboard/index.html` and open it locally in a browser. It includes **an embedded one-week subset of the original simulated results** and does not need `dashboard_data.json` or an HTTP server.

The alternate `dashboard/index.server.html` is the original interface that expects an external `dashboard_data.json`; that full file is not included, so this variant cannot be used standalone.

## Python scripts

The source scripts rely on dependencies and original input data that are not all distributed here. Use `python -m compileall -q scripts dashboard` as a syntax check; it is **not** an end-to-end execution test.

The standalone JSON export example and its test are described in [RUNNING_THE_CODE.md](RUNNING_THE_CODE.md).

## Data and permissions

No third-party input dataset becomes automatically cleared for redistribution merely because it appeared in the university submission. Confirm permissions before publishing external source datasets or team members' personal information.

See [sources and methods](SOURCES_AND_METHODS.md) for provenance and interpretation of the simulation results.
