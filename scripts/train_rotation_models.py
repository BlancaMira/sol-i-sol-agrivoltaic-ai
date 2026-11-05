"""
Sprint 2 / E04 - Entrenament de models per predir l'angle de rotacio.

Aquest fitxer compara diferents enfocaments de modelitzacio i es queda amb
el millor model segons RMSE de validacio. Esta pensat per al projecte SAMO:

    - Defineix target i features.
    - Prepara dataset de modelitzacio amb split temporal train/val/test.
    - Entrena diversos models sense dependre de scikit-learn.
    - Avalua RMSE, MAE, R2 i accuracy dins de tolerancies angulars.
    - Desa el millor model i un informe curt reproduible.

Si el dataset no conte cap columna d'angle real, pot generar un target
provisional amb agropolis_controller.py. Aixo serveix com a fallback per
tenir l'entregable funcional mentre no hi ha dades historiques del tracker.

Exemples:
    python train_rotation_models.py --data "C:/Users/blanc/Downloads/Viladecans - les Filipines - estacio.xls"
    python train_rotation_models.py --data outputs/control_full_lettuce.csv --target recommended_angle_deg
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import agropolis_controller as control


ANGLE_TARGET_CANDIDATES = [
    "best_angle_deg",
    "recommended_angle_deg",
    "tracker_mean",
    "tracker_angle",
    "angle",
    "angle_deg",
    "rotation",
    "rotation_angle",
    "rotacio",
    "rotacio_plaques",
    "rotacion",
    "angulo_rotacion",
]


FEATURE_CANDIDATES = [
    "ghi_wm2",
    "dhi_wm2",
    "dni_wm2",
    "air_temp_c",
    "soil_temp_c",
    "relative_humidity_pct",
    "wind_speed_ms",
    "precipitation_mm",
    "eto_mm",
    "solar_elevation_deg",
    "solar_azimuth_deg",
    "cos_zenith",
    "dli_reference_mol",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
    "month_sin",
    "month_cos",
    "previous_angle_deg",
    "tracker_reference_angle_deg",
    "crop_cycle_day",
    "crop_cycle_progress",
    "crop_days_to_planting",
    "crop_cycle_days_expected",
    "crop_stage_productive_num",
    "crop_stage_penalty",
    "module_transparency",
    "pitch_m",
    "gcr",
    "albedo",
    "crop_lettuce",
    "crop_tomato",
    "crop_fava",
    "crop_onion",
    "stage_establishment",
    "stage_leaf_expansion",
    "stage_harvest_window",
    "stage_summer_offseason_heat_risk",
    "stage_winter_offseason",
    "stage_vegetative",
    "stage_flowering_fruiting",
    "stage_late_crop",
    "stage_winter_vegetative",
    "stage_flowering_pods",
    "stage_initial_establishment",
    "stage_vegetative_growth",
    "stage_bulbing",
    "stage_ripening_drydown",
    "stage_late_summer_offseason",
]


@dataclass
class Metrics:
    rmse: float
    mae: float
    r2: float
    acc_5deg: float
    acc_10deg: float

    def as_dict(self) -> dict[str, float]:
        return {
            "rmse": self.rmse,
            "mae": self.mae,
            "r2": self.r2,
            "acc_5deg": self.acc_5deg,
            "acc_10deg": self.acc_10deg,
        }


class BaseModel:
    name = "base"

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "BaseModel":
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        raise NotImplementedError

    def export(self) -> dict:
        return {"name": self.name}


class MeanAngleModel(BaseModel):
    name = "mean_angle"

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "MeanAngleModel":
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        return np.full(len(x), self.mean_)

    def export(self) -> dict:
        return {"name": self.name, "mean_angle": self.mean_}


class SolarGeometryModel(BaseModel):
    name = "solar_geometry"

    def __init__(self, max_angle: float = 55.0):
        self.max_angle = max_angle

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        if frame is None or not {"sun_east", "sun_up"}.issubset(frame.columns):
            raise ValueError("solar_geometry necessita sun_east i sun_up al DataFrame.")
        angle = np.rad2deg(np.arctan2(-frame["sun_east"].to_numpy(float), frame["sun_up"].to_numpy(float)))
        angle = np.where(frame["ghi_wm2"].to_numpy(float) > 20, angle, 0.0)
        return np.clip(angle, -self.max_angle, self.max_angle)

    def export(self) -> dict:
        return {"name": self.name, "max_angle": self.max_angle}


class RidgeRegressionModel(BaseModel):
    name = "ridge_regression"

    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "RidgeRegressionModel":
        self.mean_ = x.mean(axis=0)
        self.std_ = x.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        xs = (x - self.mean_) / self.std_
        design = np.c_[np.ones(len(xs)), xs]
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coef_ = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        xs = (x - self.mean_) / self.std_
        return np.c_[np.ones(len(xs)), xs] @ self.coef_

    def export(self) -> dict:
        return {
            "name": self.name,
            "alpha": self.alpha,
            "mean": self.mean_.tolist(),
            "std": self.std_.tolist(),
            "coef": self.coef_.tolist(),
        }


class KNNRegressorModel(BaseModel):
    name = "knn_regressor"

    def __init__(self, k: int = 15, max_train: int = 5000):
        self.k = k
        self.max_train = max_train

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "KNNRegressorModel":
        if len(x) > self.max_train:
            idx = np.linspace(0, len(x) - 1, self.max_train).round().astype(int)
            x = x[idx]
            y = y[idx]
        self.mean_ = x.mean(axis=0)
        self.std_ = x.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        self.x_train_ = (x - self.mean_) / self.std_
        self.y_train_ = y.astype(float)
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        xs = (x - self.mean_) / self.std_
        preds = []
        chunk = 256
        for start in range(0, len(xs), chunk):
            block = xs[start : start + chunk]
            dist = ((block[:, None, :] - self.x_train_[None, :, :]) ** 2).sum(axis=2)
            nearest = np.argpartition(dist, kth=min(self.k, len(self.y_train_) - 1), axis=1)[:, : self.k]
            preds.append(self.y_train_[nearest].mean(axis=1))
        return np.concatenate(preds)

    def export(self) -> dict:
        return {
            "name": self.name,
            "k": self.k,
            "max_train": self.max_train,
            "mean": self.mean_.tolist(),
            "std": self.std_.tolist(),
            "x_train": self.x_train_.tolist(),
            "y_train": self.y_train_.tolist(),
        }


class BinnedRulesModel(BaseModel):
    name = "binned_rules"

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "BinnedRulesModel":
        if frame is None:
            raise ValueError("binned_rules necessita el DataFrame original.")
        tmp = frame.copy()
        tmp["_target"] = y
        tmp["_hour_bin"] = tmp["timestamp"].dt.hour
        tmp["_ghi_bin"] = pd.cut(
            tmp["ghi_wm2"],
            bins=[-1, 20, 150, 400, 700, 1200],
            labels=["night", "low", "medium", "high", "very_high"],
        ).astype(str)
        tmp["_temp_bin"] = pd.cut(
            tmp["air_temp_c"],
            bins=[-50, 10, 18, 26, 34, 80],
            labels=["cold", "mild_low", "optimal", "warm", "hot"],
        ).astype(str)
        grouped = tmp.groupby(["_hour_bin", "_ghi_bin", "_temp_bin"], dropna=False)["_target"].median()
        self.rules_ = {"|".join(map(str, k)): float(v) for k, v in grouped.items()}
        self.global_ = float(np.median(y))
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        if frame is None:
            raise ValueError("binned_rules necessita el DataFrame original.")
        tmp = frame.copy()
        hour = tmp["timestamp"].dt.hour.astype(str)
        ghi = pd.cut(
            tmp["ghi_wm2"],
            bins=[-1, 20, 150, 400, 700, 1200],
            labels=["night", "low", "medium", "high", "very_high"],
        ).astype(str)
        temp = pd.cut(
            tmp["air_temp_c"],
            bins=[-50, 10, 18, 26, 34, 80],
            labels=["cold", "mild_low", "optimal", "warm", "hot"],
        ).astype(str)
        keys = hour + "|" + ghi + "|" + temp
        return np.array([self.rules_.get(k, self.global_) for k in keys], dtype=float)

    def export(self) -> dict:
        return {"name": self.name, "global": self.global_, "rules": self.rules_}


class TrackerReferenceBiasModel(BaseModel):
    name = "tracker_reference_bias"

    def fit(self, x: np.ndarray, y: np.ndarray, frame: pd.DataFrame | None = None) -> "TrackerReferenceBiasModel":
        if frame is None or "tracker_reference_angle_deg" not in frame.columns:
            raise ValueError("tracker_reference_bias necessita tracker_reference_angle_deg.")
        ref = frame["tracker_reference_angle_deg"].to_numpy(float)
        self.bias_ = float(np.median(y - ref))
        return self

    def predict(self, x: np.ndarray, frame: pd.DataFrame | None = None) -> np.ndarray:
        if frame is None or "tracker_reference_angle_deg" not in frame.columns:
            raise ValueError("tracker_reference_bias necessita tracker_reference_angle_deg.")
        return frame["tracker_reference_angle_deg"].to_numpy(float) + self.bias_

    def export(self) -> dict:
        return {"name": self.name, "bias": self.bias_}


def slug(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("à", "a").replace("á", "a").replace("è", "e").replace("é", "e")
    text = text.replace("í", "i").replace("ò", "o").replace("ó", "o").replace("ú", "u")
    text = text.replace("ç", "c").replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def read_any_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xls", ".xlsx"}:
        return control.load_meteocat(path)
    data = pd.read_csv(path)
    data = data.rename(columns={c: slug(c) for c in data.columns})
    if "timestamp" in data.columns:
        data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    elif {"date", "time"}.issubset(data.columns):
        data["timestamp"] = pd.to_datetime(data["date"].astype(str) + " " + data["time"].astype(str), errors="coerce")
    else:
        raise ValueError("El CSV necessita una columna timestamp o date+time.")
    return data.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def is_raytrace_candidate_dataset(data: pd.DataFrame) -> bool:
    required = {"timestamp", "crop", "angle_deg", "poa_wm2", "crop_score"}
    return required.issubset(set(data.columns))


def collapse_raytrace_candidates(data: pd.DataFrame) -> pd.DataFrame:
    """Turn hour x angle x crop candidates into one supervised row per hour x crop."""
    data = data.copy()
    group_cols = ["timestamp", "crop"]
    if "timestamp_utc" in data.columns:
        group_cols.append("timestamp_utc")

    poa_max = data.groupby(group_cols)["poa_wm2"].transform("max").replace(0, np.nan)
    data["_energy_score"] = (data["poa_wm2"] / poa_max).fillna(0).clip(0, 1)
    productive = data.get("crop_stage_productive", pd.Series(True, index=data.index)).astype(float)
    stage_penalty = pd.to_numeric(data.get("crop_stage_penalty", 0), errors="coerce").fillna(0)
    data["_model_score"] = (
        0.50 * data["_energy_score"]
        + 0.35 * pd.to_numeric(data["crop_score"], errors="coerce").fillna(0)
        + 0.10 * productive
        - 0.20 * stage_penalty
        - 0.05 * (np.abs(data["angle_deg"] - data.get("tracker_reference_angle_deg", data["angle_deg"])) / 110)
    )
    idx = data.groupby(group_cols)["_model_score"].idxmax()
    best = data.loc[idx].sort_values(group_cols).reset_index(drop=True)
    best["best_angle_deg"] = best["angle_deg"].astype(float)
    best["best_candidate_score"] = best["_model_score"].astype(float)
    return best.drop(columns=[c for c in ["_energy_score", "_model_score"] if c in best.columns])


def detect_target(data: pd.DataFrame, explicit_target: str | None) -> tuple[str | None, pd.DataFrame]:
    data = data.rename(columns={c: slug(c) for c in data.columns})
    if explicit_target:
        target = slug(explicit_target)
        if target not in data.columns:
            raise ValueError(f"No trobo la columna target '{explicit_target}'. Columnes: {list(data.columns)}")
        return target, data
    for candidate in ANGLE_TARGET_CANDIDATES:
        candidate_slug = slug(candidate)
        if candidate_slug in data.columns:
            return candidate_slug, data
    return None, data


def add_solar_and_engineered_features(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    site = control.SiteConfig()
    if not {"solar_elevation_deg", "sun_east", "sun_up", "cos_zenith"}.issubset(data.columns):
        solar = control.solar_position(data["timestamp"], site)
        data = pd.concat([data.reset_index(drop=True), solar], axis=1)
    if not {"dhi_wm2", "dni_wm2"}.issubset(data.columns):
        day = data["timestamp"].dt.dayofyear.to_numpy()
        dhi, dni, _ = control.erbs_decomposition(
            data.get("ghi_wm2", pd.Series(np.zeros(len(data)))).to_numpy(float),
            data["cos_zenith"].to_numpy(float),
            day,
            data.get("solar_zenith_deg", pd.Series(np.zeros(len(data)))).to_numpy(float),
            data["timestamp"],
        )
        data["dhi_wm2"] = dhi
        data["dni_wm2"] = dni

    defaults = {
        "air_temp_c": 18.0,
        "soil_temp_c": data.get("air_temp_c", pd.Series(np.full(len(data), 18.0))),
        "relative_humidity_pct": 70.0,
        "wind_speed_ms": 0.0,
        "precipitation_mm": 0.0,
        "eto_mm": 0.0,
        "ghi_wm2": 0.0,
    }
    for col, value in defaults.items():
        if col not in data.columns:
            data[col] = value
        data[col] = pd.to_numeric(data[col], errors="coerce").ffill().bfill().fillna(0)

    indexed = data.set_index("timestamp", drop=False)
    data["dli_reference_mol"] = control.daily_light_integral(indexed["ghi_wm2"]).to_numpy()
    hour = data["timestamp"].dt.hour + data["timestamp"].dt.minute / 60
    doy = data["timestamp"].dt.dayofyear
    month = data["timestamp"].dt.month
    data["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    data["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    data["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    data["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    data["month_sin"] = np.sin(2 * np.pi * month / 12)
    data["month_cos"] = np.cos(2 * np.pi * month / 12)
    if "crop_stage_productive" in data.columns:
        data["crop_stage_productive_num"] = data["crop_stage_productive"].astype(str).str.lower().isin(["true", "1", "yes"]).astype(float)
    for col in ["crop", "crop_stage"]:
        if col in data.columns:
            dummies = pd.get_dummies(data[col].astype(str).map(slug), prefix="crop" if col == "crop" else "stage", dtype=float)
            data = pd.concat([data, dummies], axis=1)
    return data


def generate_pseudo_target(data: pd.DataFrame, crop: str) -> pd.DataFrame:
    controller_input_cols = [
        "timestamp",
        "air_temp_c",
        "soil_temp_c",
        "relative_humidity_pct",
        "wind_speed_ms",
        "precipitation_mm",
        "eto_mm",
        "ghi_wm2",
    ]
    controller_input = data[[c for c in controller_input_cols if c in data.columns]].copy()
    result = control.run_controller(
        controller_input,
        control.SiteConfig(),
        control.CROPS[crop],
        control.ObjectiveWeights(),
        step_deg=5.0,
        initial_angle=0.0,
    )
    merged = data.copy()
    merged["recommended_angle_deg"] = result["recommended_angle_deg"].to_numpy()
    return merged


def prepare_model_frame(path: Path, target: str | None, crop: str, allow_pseudo_target: bool) -> tuple[pd.DataFrame, str, bool]:
    data = read_any_dataset(path)
    if target is None and is_raytrace_candidate_dataset(data):
        data = collapse_raytrace_candidates(data)
    data = add_solar_and_engineered_features(data)
    target_col, data = detect_target(data, target)
    used_pseudo_target = False
    if target_col is None:
        if not allow_pseudo_target:
            raise ValueError("No hi ha columna d'angle i --no-pseudo-target esta activat.")
        data = generate_pseudo_target(data, crop)
        data = add_solar_and_engineered_features(data)
        target_col = "recommended_angle_deg"
        used_pseudo_target = True
    data[target_col] = pd.to_numeric(data[target_col], errors="coerce")
    data = data.dropna(subset=[target_col]).reset_index(drop=True)
    if "crop" in data.columns:
        data["previous_angle_deg"] = data.groupby("crop", sort=False)[target_col].shift(1)
    else:
        data["previous_angle_deg"] = data[target_col].shift(1)
    data["previous_angle_deg"] = data["previous_angle_deg"].ffill().bfill().fillna(0)
    return data, target_col, used_pseudo_target


def chronological_split(data: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(data)
    train_end = max(1, int(n * train_frac))
    val_end = max(train_end + 1, int(n * (train_frac + val_frac)))
    val_end = min(val_end, n - 1)
    return data.iloc[:train_end].copy(), data.iloc[train_end:val_end].copy(), data.iloc[val_end:].copy()


def make_xy(frame: pd.DataFrame, target_col: str, feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x = frame[feature_columns].to_numpy(float)
    y = frame[target_col].to_numpy(float)
    return x, y


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> Metrics:
    y_pred = np.clip(y_pred, -55, 55)
    err = y_true - y_pred
    rmse = float(np.sqrt(np.mean(err**2)))
    mae = float(np.mean(np.abs(err)))
    denom = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1 - np.sum(err**2) / denom) if denom > 0 else 0.0
    acc_5 = float(np.mean(np.abs(err) <= 5))
    acc_10 = float(np.mean(np.abs(err) <= 10))
    return Metrics(rmse, mae, r2, acc_5, acc_10)


def candidate_models() -> list[BaseModel]:
    models: list[BaseModel] = [MeanAngleModel(), SolarGeometryModel(), TrackerReferenceBiasModel()]
    models += [RidgeRegressionModel(alpha=a) for a in [0.1, 1.0, 10.0, 100.0]]
    models += [KNNRegressorModel(k=k) for k in [3, 7, 15, 31]]
    models += [BinnedRulesModel()]
    return models


def fit_and_score_models(
    train: pd.DataFrame,
    val: pd.DataFrame,
    target_col: str,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, BaseModel]:
    x_train, y_train = make_xy(train, target_col, feature_columns)
    x_val, y_val = make_xy(val, target_col, feature_columns)
    rows = []
    fitted: list[tuple[BaseModel, Metrics]] = []
    for model in candidate_models():
        try:
            model.fit(x_train, y_train, train)
            pred = model.predict(x_val, val)
            metrics = evaluate(y_val, pred)
            rows.append({"model": model.name, "params": model_param_summary(model), **metrics.as_dict()})
            fitted.append((model, metrics))
        except Exception as exc:
            rows.append({"model": model.name, "params": {"error": str(exc)}, "rmse": np.inf, "mae": np.inf, "r2": -np.inf, "acc_5deg": 0.0, "acc_10deg": 0.0})
    table = pd.DataFrame(rows).sort_values("rmse").reset_index(drop=True)
    best_model = min(fitted, key=lambda item: item[1].rmse)[0]
    return table, best_model


def model_param_summary(model: BaseModel) -> dict:
    if isinstance(model, RidgeRegressionModel):
        return {"alpha": model.alpha}
    if isinstance(model, KNNRegressorModel):
        return {"k": model.k, "max_train": model.max_train}
    if isinstance(model, SolarGeometryModel):
        return {"max_angle": model.max_angle}
    if isinstance(model, TrackerReferenceBiasModel):
        return {"bias": getattr(model, "bias_", None)}
    return {}


def refit_same_model(best_model: BaseModel, train_val: pd.DataFrame, target_col: str, feature_columns: list[str]) -> BaseModel:
    exported = best_model.export()
    name = exported["name"]
    if name == "mean_angle":
        model: BaseModel = MeanAngleModel()
    elif name == "solar_geometry":
        model = SolarGeometryModel(max_angle=exported.get("max_angle", 55.0))
    elif name == "ridge_regression":
        model = RidgeRegressionModel(alpha=exported.get("alpha", 10.0))
    elif name == "knn_regressor":
        model = KNNRegressorModel(k=exported.get("k", 15), max_train=exported.get("max_train", 5000))
    elif name == "binned_rules":
        model = BinnedRulesModel()
    elif name == "tracker_reference_bias":
        model = TrackerReferenceBiasModel()
    else:
        raise ValueError(f"Model desconegut: {name}")
    x, y = make_xy(train_val, target_col, feature_columns)
    return model.fit(x, y, train_val)


def save_best_model(
    model: BaseModel,
    output_dir: Path,
    target_col: str,
    feature_columns: list[str],
    validation_metrics: dict,
    test_metrics: dict,
    used_pseudo_target: bool,
) -> Path:
    meta = {
        "target_col": target_col,
        "feature_columns": feature_columns,
        "model": model.export(),
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "used_pseudo_target": used_pseudo_target,
        "angle_unit": "degrees",
    }
    path = output_dir / "best_rotation_model.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_report(
    output_dir: Path,
    metrics_table: pd.DataFrame,
    best_name: str,
    target_col: str,
    used_pseudo_target: bool,
    test_metrics: Metrics,
    feature_columns: list[str],
) -> Path:
    report = output_dir / "rotation_model_report.md"
    target_note = (
        "Target provisional generat pel controlador multiobjectiu, perquè el dataset no contenia angle històric real."
        if used_pseudo_target
        else f"Target històric detectat: `{target_col}`."
    )
    lines = [
        "# Informe Sprint 2 - Model de prediccio de rotacio",
        "",
        "## Target i dades",
        "",
        target_note,
        "",
        "## Models comparats",
        "",
        "- Mitjana historica d'angle.",
        "- Geometria solar simple.",
        "- Referencia fisica del tracker amb biaix apres.",
        "- Regressio Ridge amb diferents regularitzacions.",
        "- KNN regressor amb diversos valors de k.",
        "- Regles interpretables per franges d'hora, irradiancia i temperatura.",
        "",
        "## Millor model",
        "",
        f"`{best_name}`",
        "",
        "## Metriques en test",
        "",
        f"- RMSE: {test_metrics.rmse:.3f} graus",
        f"- MAE: {test_metrics.mae:.3f} graus",
        f"- R2: {test_metrics.r2:.3f}",
        f"- Accuracy ±5 graus: {test_metrics.acc_5deg:.1%}",
        f"- Accuracy ±10 graus: {test_metrics.acc_10deg:.1%}",
        "",
        "## Ranking de validacio",
        "",
        markdown_metrics_table(metrics_table[["model", "rmse", "mae", "r2", "acc_5deg", "acc_10deg"]]),
        "",
        "## Features utilitzades",
        "",
        ", ".join(f"`{c}`" for c in feature_columns),
        "",
        "## Limitacions i proxims passos",
        "",
        "- Si el target es provisional, les metriques mesuren la capacitat d'imitar la politica optima generada, no un tracker real.",
        "- Quan hi hagi angle historic real, executar amb `--target nom_columna_angle`.",
        "- Per al dashboard, carregar el JSON del millor model o usar el CSV de prediccions generat.",
        "- Si l'entrada es un dataset `hora x angle x cultiu` (`ground_scan_all_crops.csv` o antic `raytrace_all_crops.csv`), es col·lapsa primer a una fila per hora i cultiu amb `best_angle_deg`.",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def markdown_metrics_table(table: pd.DataFrame) -> str:
    headers = list(table.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in table.iterrows():
        values = []
        for col in headers:
            value = row[col]
            if isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Entrena diversos models i selecciona el millor predictor d'angle.")
    parser.add_argument("--data", type=Path, required=True, help="CSV/XLS amb sensors i, idealment, angle historic.")
    parser.add_argument("--target", type=str, default=None, help="Nom de la columna d'angle a predir.")
    parser.add_argument("--crop", choices=sorted(control.CROPS), default="lettuce", help="Cultiu per al target provisional.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/rotation_model_selection"))
    parser.add_argument("--no-pseudo-target", action="store_true", help="Falla si no hi ha angle historic real.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    data, target_col, used_pseudo_target = prepare_model_frame(
        args.data,
        args.target,
        args.crop,
        allow_pseudo_target=not args.no_pseudo_target,
    )
    feature_columns = [c for c in FEATURE_CANDIDATES if c in data.columns]
    data = data.dropna(subset=feature_columns + [target_col]).reset_index(drop=True)
    if len(data) < 30:
        raise ValueError("Calen almenys 30 files valides per entrenar i validar models.")

    train, val, test = chronological_split(data)
    metrics_table, best_val_model = fit_and_score_models(train, val, target_col, feature_columns)
    train_val = pd.concat([train, val], ignore_index=True)
    best_model = refit_same_model(best_val_model, train_val, target_col, feature_columns)

    x_test, y_test = make_xy(test, target_col, feature_columns)
    test_pred = np.clip(best_model.predict(x_test, test), -55, 55)
    test_metrics = evaluate(y_test, test_pred)

    predictions = test[["timestamp", target_col]].copy()
    for extra_col in ["timestamp_utc", "crop", "crop_stage", "crop_cycle_progress", "crop_stage_productive", "tracker_reference_angle_deg"]:
        if extra_col in test.columns:
            predictions[extra_col] = test[extra_col].to_numpy()
    predictions["predicted_angle_deg"] = test_pred
    predictions["abs_error_deg"] = np.abs(predictions[target_col] - predictions["predicted_angle_deg"])

    metrics_csv = args.out_dir / "model_metrics_validation.csv"
    predictions_csv = args.out_dir / "test_predictions_best_model.csv"
    metrics_table.to_csv(metrics_csv, index=False)
    predictions.to_csv(predictions_csv, index=False)

    best_json = save_best_model(
        best_model,
        args.out_dir,
        target_col,
        feature_columns,
        metrics_table.iloc[0].drop(labels=["params"]).to_dict(),
        test_metrics.as_dict(),
        used_pseudo_target,
    )
    report = write_report(
        args.out_dir,
        metrics_table,
        best_model.name,
        target_col,
        used_pseudo_target,
        test_metrics,
        feature_columns,
    )

    print(
        {
            "rows": len(data),
            "target": target_col,
            "used_pseudo_target": used_pseudo_target,
            "best_model": best_model.name,
            "test_rmse": round(test_metrics.rmse, 3),
            "test_mae": round(test_metrics.mae, 3),
            "model_file": str(best_json),
            "report": str(report),
            "predictions": str(predictions_csv),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
