"""Generate synthetic agri-PV scenarios for DSS/data augmentation.

The goal is not to invent validated field observations. The script perturbs
real Meteocat rows within auditable ranges, runs the existing multi-objective
controller, and exports additional labelled scenarios for stress-testing,
model training, and future crop/panel exploration.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agropolis_controller as control  # noqa: E402

PANEL_TYPES = {
    "semi_transparent": {"label": "Semitransparent 40%", "module_transparency": 0.40, "bifacial_gain": 0.03},
    "standard": {"label": "Estàndard 10%", "module_transparency": 0.10, "bifacial_gain": 0.03},
    "high_transparency": {"label": "Alta transparència 60%", "module_transparency": 0.60, "bifacial_gain": 0.025},
}

DEFAULT_METEO = ROOT / "outputs" / "control_full_lettuce_robust.csv"
DEFAULT_OUT = ROOT / "outputs" / "synthetic_agriPV_scenarios.csv"


def _clip(series: pd.Series, low: float, high: float) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").clip(lower=low, upper=high)


def build_synthetic_meteo(meteo: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Sample observed weather rows and perturb them into plausible scenarios."""
    rng = np.random.default_rng(seed)
    base = meteo.sample(n=n, replace=True, random_state=seed).reset_index(drop=True).copy()
    base["scenario_id"] = [f"syn_{i:05d}" for i in range(n)]
    base["source_timestamp"] = base["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    hour = base["timestamp"].dt.hour.to_numpy()
    daylight = ((hour >= 6) & (hour <= 21)).astype(float)

    temp_delta = rng.normal(0, 3.0, n)
    heatwave = rng.random(n) < 0.12
    cold_snap = rng.random(n) < 0.08
    temp_delta += heatwave * rng.uniform(3.0, 7.0, n)
    temp_delta -= cold_snap * rng.uniform(2.0, 5.0, n)

    irradiance_factor = rng.lognormal(mean=0.0, sigma=0.22, size=n)
    cloudy = rng.random(n) < 0.18
    irradiance_factor = np.where(cloudy, irradiance_factor * rng.uniform(0.25, 0.75, n), irradiance_factor)

    dry = rng.random(n) < 0.20
    rainy = rng.random(n) < 0.10

    base["air_temp_c"] = _clip(base["air_temp_c"] + temp_delta, -5, 45)
    base["soil_temp_c"] = _clip(base.get("soil_temp_c", base["air_temp_c"]) + temp_delta * 0.55 + rng.normal(0, 1.0, n), -2, 40)
    base["relative_humidity_pct"] = _clip(base.get("relative_humidity_pct", 70) + rng.normal(0, 10, n) - heatwave * 8 + rainy * 12, 20, 100)
    base["wind_speed_ms"] = _clip(base.get("wind_speed_ms", 0) + rng.gamma(1.4, 0.6, n) + (rng.random(n) < 0.06) * rng.uniform(4, 8, n), 0, 16)
    base["precipitation_mm"] = _clip(base.get("precipitation_mm", 0) * rng.uniform(0.3, 1.8, n) + rainy * rng.gamma(1.5, 2.0, n), 0, 40)
    base["eto_mm"] = _clip(base.get("eto_mm", 0.1) + daylight * (base["air_temp_c"] - 18).clip(lower=0) * 0.015 + dry * 0.25, 0, 8)
    base["ghi_wm2"] = _clip(base["ghi_wm2"] * irradiance_factor * daylight, 0, 1100)

    base["augmentation_label"] = np.select(
        [heatwave, cold_snap, cloudy, dry, rainy, base["wind_speed_ms"].to_numpy() >= 10],
        ["heatwave", "cold_snap", "cloudy", "dry", "rainy", "wind_stow_risk"],
        default="nominal_perturbation",
    )
    base["synthetic"] = True
    return base


def load_weather_source(path: Path) -> pd.DataFrame:
    """Load raw Meteocat XLS/CSV or an already-normalized controller CSV."""
    if path.suffix.lower() in {".xls", ".xlsx"}:
        return control.load_meteocat(path)
    data = pd.read_csv(path)
    if "timestamp" not in data.columns:
        return control.load_meteocat(path)
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    if "timestamp_utc" in data.columns:
        data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], errors="coerce", utc=True)
    needed_defaults = {
        "air_temp_c": 18.0,
        "soil_temp_c": 18.0,
        "relative_humidity_pct": 70.0,
        "wind_speed_ms": 0.0,
        "precipitation_mm": 0.0,
        "eto_mm": 0.0,
        "ghi_wm2": 0.0,
    }
    for col, default in needed_defaults.items():
        if col not in data.columns:
            data[col] = default
    keep_cols = ["timestamp", "timestamp_utc", *needed_defaults.keys()]
    return data[[c for c in keep_cols if c in data.columns]].dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def generate_scenarios(meteo_path: Path, n: int, seed: int, crops: list[str], panels: list[str]) -> pd.DataFrame:
    meteo = load_weather_source(meteo_path)
    synthetic_meteo = build_synthetic_meteo(meteo, n=n, seed=seed)
    rows: list[pd.DataFrame] = []

    for crop_key in crops:
        for panel_key in panels:
            panel = PANEL_TYPES[panel_key]
            site = replace(
                control.SiteConfig(),
                module_transparency=panel["module_transparency"],
                bifacial_gain=panel["bifacial_gain"],
            )
            result = control.run_controller(
                synthetic_meteo,
                site,
                control.CROPS[crop_key],
                control.ObjectiveWeights(),
                step_deg=5.0,
                initial_angle=0.0,
            )
            result.insert(0, "scenario_id", synthetic_meteo["scenario_id"].to_numpy())
            result.insert(1, "synthetic", True)
            result.insert(2, "augmentation_label", synthetic_meteo["augmentation_label"].to_numpy())
            result.insert(3, "source_timestamp", synthetic_meteo["source_timestamp"].to_numpy())
            result.insert(4, "crop", crop_key)
            result.insert(5, "panel_type", panel_key)
            result.insert(6, "panel_label", panel["label"])
            result["module_transparency"] = panel["module_transparency"]
            result["bifacial_gain"] = panel["bifacial_gain"]
            rows.append(result)

    return pd.concat(rows, ignore_index=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera escenaris sintètics agri-PV per data augmentation i DSS.")
    parser.add_argument("--meteo-xls", type=Path, default=DEFAULT_METEO)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--n", type=int, default=240, help="Nombre de files Meteocat sintètiques abans de creuar cultius/panells.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--crops", nargs="+", choices=sorted(control.CROPS), default=sorted(control.CROPS))
    parser.add_argument("--panels", nargs="+", choices=sorted(PANEL_TYPES), default=sorted(PANEL_TYPES))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = generate_scenarios(args.meteo_xls, args.n, args.seed, args.crops, args.panels)
    data.to_csv(args.out, index=False)
    print({"output": str(args.out), "rows": int(len(data)), "synthetic_base_rows": args.n})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
