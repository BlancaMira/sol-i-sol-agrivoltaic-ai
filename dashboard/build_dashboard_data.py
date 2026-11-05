from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agropolis_controller as control  # noqa: E402


METEO_XLS = ROOT / "data" / "raw" / "Viladecans - les Filipines - estacio.xls"
OUT = Path(__file__).resolve().with_name("dashboard_data.json")
MODEL_JSON = ROOT / "outputs" / "rotation_model_selection_robust_raytrace" / "best_rotation_model.json"
GROUND_SCAN_CSV = ROOT / "outputs" / "ground_scan_all_crops.csv"
RAYTRACE_CSV = GROUND_SCAN_CSV if GROUND_SCAN_CSV.exists() else ROOT / "outputs" / "raytrace_all_crops.csv"

PANEL_TYPES = {
    "semi_transparent": {
        "label": "Semitransparent 40%",
        "module_transparency": 0.40,
        "bifacial_gain": 0.03,
        "description": "Opcio representativa SYMBIOSYST per compatibilitzar llum al cultiu i energia.",
    },
    "standard": {
        "label": "Estàndard 10%",
        "module_transparency": 0.10,
        "bifacial_gain": 0.03,
        "description": "Mes opaca: normalment dona mes energia i mes ombra al cultiu.",
    },
    "high_transparency": {
        "label": "Alta transparència 60%",
        "module_transparency": 0.60,
        "bifacial_gain": 0.025,
        "description": "Mes llum per al cultiu, amb una penalitzacio energetica simplificada.",
    },
}


def compact_float(value: float | int | None, digits: int = 3) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def build_raytrace_lookup() -> dict[tuple[str, str, float], dict]:
    if not RAYTRACE_CSV.exists():
        return {}
    usecols = [
        "timestamp",
        "crop",
        "angle_deg",
        "ground_mean_wm2",
        "ground_uniformity",
        "ground_p10_wm2",
        "ground_p90_wm2",
        "raytrace_engine",
        "radiance_executables",
    ]
    data = pd.read_csv(RAYTRACE_CSV, usecols=usecols)
    data["t"] = pd.to_datetime(data["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
    data["angle_key"] = (pd.to_numeric(data["angle_deg"], errors="coerce") / 10).round() * 10
    lookup = {}
    for _, row in data.iterrows():
        lookup[(row["crop"], row["t"], float(row["angle_key"]))] = {
            "ground_mean": compact_float(row["ground_mean_wm2"], 1),
            "ground_uniformity": compact_float(row["ground_uniformity"], 3),
            "ground_p10": compact_float(row["ground_p10_wm2"], 1),
            "ground_p90": compact_float(row["ground_p90_wm2"], 1),
            "raytrace_engine": str(row["raytrace_engine"]),
            "radiance_executables": bool(row["radiance_executables"]),
        }
    return lookup


def build_records() -> dict:
    meteo = control.load_meteocat(METEO_XLS)
    raytrace_lookup = build_raytrace_lookup()
    # El dashboard no necessita tots els camps crus, pero si tota la serie horaria.
    payload: dict[str, object] = {
        "generated_from": str(METEO_XLS),
        "raytrace_dataset": str(RAYTRACE_CSV) if RAYTRACE_CSV.exists() else None,
        "model_file": str(MODEL_JSON) if MODEL_JSON.exists() else None,
        "model": json.loads(MODEL_JSON.read_text(encoding="utf-8")) if MODEL_JSON.exists() else None,
        "date_min": meteo["timestamp"].min().strftime("%Y-%m-%d %H:%M"),
        "date_max": meteo["timestamp"].max().strftime("%Y-%m-%d %H:%M"),
        "crops": {
            "lettuce": {"label": "Enciam", "color": "#61b15a", "shape": "leafy"},
            "tomato": {"label": "Tomàquet", "color": "#d94b3d", "shape": "vine"},
            "fava": {"label": "Faves", "color": "#76a857", "shape": "stems"},
            "onion": {"label": "Ceba", "color": "#b58a4a", "shape": "bulbs"},
        },
        "panel_types": PANEL_TYPES,
        "series": {},
    }

    for crop_name in payload["crops"]:
        payload["series"][crop_name] = {}
        for panel_key, panel in PANEL_TYPES.items():
            site = replace(
                control.SiteConfig(),
                module_transparency=panel["module_transparency"],
                bifacial_gain=panel["bifacial_gain"],
            )
            result = control.run_controller(
                meteo,
                site,
                control.CROPS[crop_name],
                control.ObjectiveWeights(),
                step_deg=5.0,
                initial_angle=0.0,
            )
            records = []
            for _, row in result.iterrows():
                planting = control.planting_date_for_cycle(control.CROPS[crop_name], row["timestamp"])
                harvest = planting + pd.Timedelta(days=control.CROPS[crop_name].cycle_days)
                angle_key = round(float(row["recommended_angle_deg"]) / 10) * 10
                rt = raytrace_lookup.get((crop_name, row["timestamp"].strftime("%Y-%m-%d %H:%M"), float(angle_key)), {})
                records.append(
                    {
                        "t": row["timestamp"].strftime("%Y-%m-%d %H:%M"),
                        "tu": row["timestamp_utc"].strftime("%Y-%m-%d %H:%M") if "timestamp_utc" in row and pd.notna(row["timestamp_utc"]) else None,
                        "ghi": compact_float(row["ghi_wm2"], 1),
                        "temp": compact_float(row["air_temp_c"], 1),
                        "soil": compact_float(row["soil_temp_c"], 1),
                        "hum": compact_float(row["relative_humidity_pct"], 1),
                        "wind": compact_float(row["wind_speed_ms"], 1),
                        "rain": compact_float(row["precipitation_mm"], 2),
                        "angle": compact_float(row["recommended_angle_deg"], 1),
                        "tracker_ref": compact_float(row.get("tracker_reference_angle_deg"), 1),
                        "angle_delta_vs_tracker": compact_float(row.get("angle_delta_vs_tracker_deg"), 1),
                        "poa": compact_float(row["poa_wm2"], 1),
                        "reference_poa": compact_float(row.get("reference_poa_wm2"), 1),
                        "crop_irrad": compact_float(row["crop_irradiance_wm2"], 1),
                        "reference_crop_irrad": compact_float(row.get("reference_crop_irradiance_wm2"), 1),
                        "energy_loss_vs_tracker": compact_float(row.get("energy_loss_vs_tracker_pct"), 2),
                        "crop_light_delta_vs_tracker": compact_float(row.get("crop_light_delta_vs_tracker_pct"), 2),
                        "energy": compact_float(row["energy_score"], 3),
                        "crop_score": compact_float(row["crop_score"], 3),
                        "move": compact_float(row["movement_penalty"], 3),
                        "effective_energy_weight": compact_float(row.get("effective_energy_weight"), 3),
                        "effective_crop_weight": compact_float(row.get("effective_crop_weight"), 3),
                        "effective_movement_weight": compact_float(row.get("effective_movement_weight"), 3),
                        "crop_stress": compact_float(row.get("crop_stress"), 3),
                        "temp_air_stress": compact_float(row.get("temp_air_stress"), 3),
                        "temp_soil_stress": compact_float(row.get("temp_soil_stress"), 3),
                        "water_stress": compact_float(row.get("water_stress"), 3),
                        "heat_light_stress": compact_float(row.get("heat_light_stress"), 3),
                        "light_deficit_stress": compact_float(row.get("light_deficit_stress"), 3),
                        "crop_kc": compact_float(row.get("crop_kc"), 3),
                        "etc_mm": compact_float(row.get("etc_mm"), 3),
                        "crop_stage": str(row.get("crop_stage", "")),
                        "crop_cycle_day": compact_float(row.get("crop_cycle_day"), 0),
                        "crop_cycle_progress": compact_float(row.get("crop_cycle_progress"), 3),
                        "crop_days_to_planting": compact_float(row.get("crop_days_to_planting"), 0),
                        "crop_cycle_days_expected": control.CROPS[crop_name].cycle_days,
                        "planting_date": planting.strftime("%Y-%m-%d"),
                        "harvest_date": harvest.strftime("%Y-%m-%d"),
                        "days_to_harvest": max(0, int((harvest - row["timestamp"].normalize()).days)),
                        "crop_stage_productive": bool(row.get("crop_stage_productive", True)),
                        **rt,
                        "reason": str(row["reason"]),
                    }
                )
            payload["series"][crop_name][panel_key] = records
    return payload


def main() -> int:
    payload = build_records()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print({"output": str(OUT), "size_bytes": OUT.stat().st_size})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
