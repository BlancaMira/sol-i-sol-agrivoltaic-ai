# Run the currently published sample

The source code is a university proof of concept. The **small JSON fixture in `examples/` is synthetic**, created to illustrate the output contract; it is not part of the real-world training datasets.

From the repository root:

```bash
python -m venv .venv
# On macOS/Linux:
source .venv/bin/activate
# On Windows PowerShell:
# .venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python scripts/export_control_policy.py --dashboard-data examples/dashboard_data.sample.json --comparison examples/nonexistent.csv --crop tomato --panel semi_transparent --out outputs/sample_policy.json
python -m unittest discover -s tests -v
```

The export command reads a single sample record and writes a JSON recommendation. **It does not command hardware.** The example uses a fictitious observation and is intended as a smoke test.

The rest of the original coursework scripts (controller, model training, comparison and synthetic scenario generation) require additional input data and dependency checks. They are being curated separately. No end-to-end reproduction is claimed yet.
