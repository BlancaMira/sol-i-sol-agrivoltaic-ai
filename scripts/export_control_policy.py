"""Export a simple DSS-to-control JSON policy message.

This does not actuate a real pilot plant. It defines the machine-readable
contract that a real agri-PV controller could consume after validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD = ROOT / "dashboard" / "dashboard_data.json"
DEFAULT_COMPARISON = ROOT / "outputs" / "dss_model_comparison.csv"
DEFAULT_OUT = ROOT / "outputs" / "control_policy_api_example.json"


def load_record(payload: dict, crop: str, panel: str, timestamp: str | None) -> dict:
    records = payload["series"][crop][panel]
    if not records:
        raise ValueError(f"No hi ha registres per crop={crop}, panel={panel}")
    if timestamp is None:
        return records[len(records) // 2]
    target = pd.to_datetime(timestamp)
    frame = pd.DataFrame(records)
    frame["_t"] = pd.to_datetime(frame["t"])
    idx = (frame["_t"] - target).abs().idxmin()
    return records[int(idx)]


def comparison_context(comparison_path: Path, crop: str, timestamp: str) -> dict:
    if not comparison_path.exists():
        return {}
    data = pd.read_csv(comparison_path)
    if "crop" in data.columns:
        data = data[data["crop"] == crop]
    if data.empty or "timestamp" not in data.columns:
        return {}
    target = pd.to_datetime(timestamp)
    data["_t"] = pd.to_datetime(data["timestamp"])
    row = data.loc[(data["_t"] - target).abs().idxmin()]
    return {
        "ml_predicted_angle_deg": round(float(row.get("ml_predicted_angle_deg", 0)), 2),
        "bio_vs_ml_abs_difference_deg": round(float(row.get("abs_angle_difference_deg", 0)), 2),
        "dss_match_band": str(row.get("dss_match_band", "unknown")),
        "main_disagreement_reason": str(row.get("main_disagreement_reason", "not_available")),
        "top_ml_drivers": str(row.get("top_ml_drivers", "not_available")),
    }


def control_mode(record: dict) -> str:
    reason = str(record.get("reason", ""))
    wind = float(record.get("wind") or 0)
    ghi = float(record.get("ghi") or 0)
    if reason == "wind_stow" or wind >= 10:
        return "wind_stow"
    if reason == "night_idle" or ghi <= 20:
        return "night_idle"
    return "optimized_tracking"


def build_policy(dashboard_path: Path, comparison_path: Path, crop: str, panel: str, timestamp: str | None) -> dict:
    payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    record = load_record(payload, crop, panel, timestamp)
    dss = comparison_context(comparison_path, crop, record["t"])
    policy = {
        "schema": "samo.agri_pv.control_policy.v1",
        "generated_by": "SOL I SOL DSS prototype",
        "source_dashboard_data": str(dashboard_path.relative_to(ROOT) if dashboard_path.is_absolute() and ROOT in dashboard_path.parents else dashboard_path),
        "timestamp_local": record["t"],
        "timestamp_utc": record.get("tu"),
        "site": {
            "name": "Agròpolis Viladecans",
            "timezone": "Europe/Madrid",
            "angle_sign_convention": "negative_morning_east_positive_afternoon_west",
        },
        "context": {
            "crop": crop,
            "panel_type": panel,
            "ghi_wm2": record.get("ghi"),
            "air_temp_c": record.get("temp"),
            "soil_temp_c": record.get("soil"),
            "relative_humidity_pct": record.get("hum"),
            "wind_speed_ms": record.get("wind"),
            "crop_stage": record.get("crop_stage"),
            "crop_cycle_progress": record.get("crop_cycle_progress"),
        },
        "decision": {
            "recommended_angle_deg": record.get("angle"),
            "tracker_reference_angle_deg": record.get("tracker_ref"),
            "mode": control_mode(record),
            "reason": record.get("reason"),
            "energy_score": record.get("energy"),
            "crop_score": record.get("crop_score"),
            "movement_penalty": record.get("move"),
        },
        "constraints": {
            "max_angle_deg": 55,
            "max_step_deg_per_hour": 15,
            "night_idle_when_low_irradiance": True,
            "wind_stow_threshold_ms": 10,
            "requires_human_validation_before_real_actuation": True,
        },
        "dss_validation": dss,
    }
    return policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exporta un missatge JSON DSS -> control agri-PV.")
    parser.add_argument("--dashboard-data", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--crop", choices=["lettuce", "tomato", "fava", "onion"], default="tomato")
    parser.add_argument("--panel", choices=["semi_transparent", "standard", "high_transparency"], default="semi_transparent")
    parser.add_argument("--timestamp", type=str, default="2025-07-18 14:00")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy = build_policy(args.dashboard_data, args.comparison, args.crop, args.panel, args.timestamp)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8")
    print({"output": str(args.out), "timestamp_local": policy["timestamp_local"], "angle": policy["decision"]["recommended_angle_deg"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
