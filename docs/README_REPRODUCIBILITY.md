# Reproducibility note

This bundle contains all five source scripts and the original HTML/CSS/JS dashboard plus the builder scripts and technical report. The original large input datasets and full generated outputs have been excluded. A **one-week filtered subset of the original generated output** is included in `dashboard/dashboard_data.json` for a lightweight preview. This is not an independently created synthetic input, nor does it reproduce all the original submitted time series. Open from a local HTTP server; browsers may block local `fetch` on a `file://` URL. Check the original report for environment assumptions and source provenance.

No third-party dataset is cleared for redistribution by inclusion in the original coursework ZIP. Obtain permission before publishing original input datasets or the full submission with teammates' personal information.

Run `python -m compileall -q scripts dashboard` for syntax sanity. This is not an end-to-end execution test.
