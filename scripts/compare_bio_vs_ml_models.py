"""Compare the biological/physical controller target with the data-driven model.

This creates a DSS artefact that explicitly reports matches and disagreements
between the literature-inspired controller score and the learned angle model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import train_rotation_models as models  # noqa: E402

DEFAULT_DATA = ROOT / "outputs" / "ground_scan_all_crops.csv"
DEFAULT_MODEL = ROOT / "outputs" / "rotation_model_selection_robust_raytrace" / "best_rotation_model.json"
DEFAULT_OUT = ROOT / "outputs" / "dss_model_comparison.csv"
DEFAULT_REPORT = ROOT / "outputs" / "dss_model_comparison_report.md"


def predict_from_export(frame: pd.DataFrame, meta: dict) -> np.ndarray:
    model = meta["model"]
    name = model.get("name")
    features = meta["feature_columns"]
    prepared = frame.copy()
    for col in features:
        if col not in prepared.columns:
            prepared[col] = 0.0
    x = prepared[features].to_numpy(float)

    if name == "ridge_regression":
        mean = np.asarray(model["mean"], dtype=float)
        std = np.asarray(model["std"], dtype=float)
        std[std == 0] = 1.0
        coef = np.asarray(model["coef"], dtype=float)
        xs = (x - mean) / std
        pred = np.c_[np.ones(len(xs)), xs] @ coef
        return np.clip(pred, -55, 55)

    if name == "tracker_reference_bias":
        return np.clip(prepared["tracker_reference_angle_deg"].to_numpy(float) + float(model.get("bias", 0.0)), -55, 55)

    if name == "solar_geometry":
        max_angle = float(model.get("max_angle", 55.0))
        angle = np.where(prepared.get("sun_up", 1).to_numpy(float) > 0, np.tanh(prepared["solar_azimuth_deg"].to_numpy(float) / 55.0) * max_angle, 0.0)
        return np.clip(angle, -55, 55)

    if name == "mean_angle":
        return np.full(len(prepared), float(model.get("mean_angle", 0.0)))

    raise ValueError(f"Model exportat no suportat per aquest comparador DSS: {name}")


def top_ridge_drivers(frame: pd.DataFrame, meta: dict, top_n: int = 3) -> list[str]:
    model = meta["model"]
    features = meta["feature_columns"]
    if model.get("name") != "ridge_regression":
        return ["model_no_lineal_o_no_ridge"] * len(frame)
    prepared = frame.copy()
    for col in features:
        if col not in prepared.columns:
            prepared[col] = 0.0
    x = prepared[features].to_numpy(float)
    mean = np.asarray(model["mean"], dtype=float)
    std = np.asarray(model["std"], dtype=float)
    std[std == 0] = 1.0
    coef = np.asarray(model["coef"], dtype=float)[1:]
    contrib = ((x - mean) / std) * coef
    labels: list[str] = []
    feature_arr = np.asarray(features)
    for row in np.abs(contrib):
        idx = np.argsort(row)[-top_n:][::-1]
        labels.append(", ".join(feature_arr[idx]))
    return labels


def disagreement_reason(row: pd.Series) -> str:
    diff = abs(float(row["angle_difference_deg"]))
    if diff <= 5:
        return "match_within_5deg"
    if diff <= 10:
        return "minor_difference_5_10deg"
    if row.get("wind_speed_ms", 0) >= 10:
        return "controller_prioritizes_wind_stow"
    if row.get("crop_stress", 0) >= 0.45:
        return "controller_prioritizes_crop_stress"
    if abs(row.get("tracker_reference_angle_deg", row["bio_recommended_angle_deg"]) - row["bio_recommended_angle_deg"]) > 10:
        return "controller_deviates_from_solar_tracker_for_multiobjective_tradeoff"
    return "ml_controller_policy_disagreement"


def build_comparison(data_path: Path, model_path: Path, max_rows: int | None) -> pd.DataFrame:
    data = models.read_any_dataset(data_path)
    if models.is_raytrace_candidate_dataset(data):
        data = models.collapse_raytrace_candidates(data)
    data = models.add_solar_and_engineered_features(data)
    data["previous_angle_deg"] = data.groupby("crop", sort=False)["best_angle_deg"].shift(1).ffill().bfill().fillna(0) if "crop" in data else data["best_angle_deg"].shift(1).ffill().bfill().fillna(0)
    if max_rows:
        data = data.head(max_rows).copy()

    meta = json.loads(model_path.read_text(encoding="utf-8"))
    data["ml_predicted_angle_deg"] = predict_from_export(data, meta)
    data["bio_recommended_angle_deg"] = pd.to_numeric(data["best_angle_deg"], errors="coerce")
    data["angle_difference_deg"] = data["ml_predicted_angle_deg"] - data["bio_recommended_angle_deg"]
    data["abs_angle_difference_deg"] = data["angle_difference_deg"].abs()
    data["dss_match_band"] = pd.cut(
        data["abs_angle_difference_deg"],
        bins=[-0.001, 5, 10, 20, 999],
        labels=["match_0_5deg", "near_5_10deg", "disagreement_10_20deg", "strong_disagreement_gt20deg"],
    ).astype(str)
    data["main_disagreement_reason"] = data.apply(disagreement_reason, axis=1)
    data["top_ml_drivers"] = top_ridge_drivers(data, meta)

    keep = [
        "timestamp", "timestamp_utc", "crop", "crop_stage", "crop_cycle_progress", "crop_stage_productive",
        "bio_recommended_angle_deg", "ml_predicted_angle_deg", "angle_difference_deg", "abs_angle_difference_deg",
        "dss_match_band", "main_disagreement_reason", "top_ml_drivers", "tracker_reference_angle_deg",
        "best_candidate_score", "poa_wm2", "crop_irradiance_wm2", "crop_score", "crop_stress",
        "energy_score", "ghi_wm2", "air_temp_c", "soil_temp_c", "relative_humidity_pct", "wind_speed_ms",
        "module_transparency", "gcr", "raytrace_engine",
    ]
    return data[[c for c in keep if c in data.columns]].sort_values(["timestamp", "crop"]).reset_index(drop=True)


def write_report(comparison: pd.DataFrame, model_path: Path, report_path: Path) -> None:
    rows = len(comparison)
    mean_abs = comparison["abs_angle_difference_deg"].mean()
    match5 = (comparison["abs_angle_difference_deg"] <= 5).mean()
    match10 = (comparison["abs_angle_difference_deg"] <= 10).mean()
    band_counts = comparison["dss_match_band"].value_counts().to_dict()
    reason_counts = comparison["main_disagreement_reason"].value_counts().head(8).to_dict()
    lines = [
        "# DSS - Comparació model biològic/físic vs model data-driven",
        "",
        "Aquest informe converteix el treball existent en una peça explícita de DSS per a licitació.",
        "El model biològic/físic és el controlador multiobjectiu aplicat al dataset de candidats; el model data-driven és el millor model exportat.",
        "",
        "## Resultats globals",
        "",
        f"- Files comparades: {rows}",
        f"- Model data-driven: `{model_path.relative_to(ROOT) if model_path.is_absolute() and ROOT in model_path.parents else model_path}`",
        f"- Diferència absoluta mitjana: {mean_abs:.2f} graus",
        f"- Coincidència ±5 graus: {match5:.1%}",
        f"- Coincidència ±10 graus: {match10:.1%}",
        "",
        "## Bandes de coincidència",
        "",
    ]
    for key, value in band_counts.items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Principales razones de desacuerdo", ""]
    for key, value in reason_counts.items():
        lines.append(f"- {key}: {value}")
    lines += [
        "",
        "## Interpretación",
        "",
        "Las filas con desacuerdo fuerte son candidatas para revisión agronómica o de control: pueden señalar situaciones donde el modelo aprendido suaviza o no replica restricciones explícitas del controlador, como estrés del cultivo, viento o desviación deliberada respecto al tracker solar puro.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compara controlador biològic/físic i model data-driven per al DSS.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-rows", type=int, default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    comparison = build_comparison(args.data, args.model, args.max_rows)
    comparison.to_csv(args.out, index=False)
    write_report(comparison, args.model, args.report)
    print({"output": str(args.out), "report": str(args.report), "rows": int(len(comparison))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
