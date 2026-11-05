"""
Controlador multiobjectiu per a trackers agrivoltaics a Agròpolis Viladecans.

El model avalua angles candidats del tracker i recomana l'angle que millor
equilibra energia PV, llum/benestar del cultiu i suavitat de moviment.

Entrada principal:
    - CSV/XLS Meteocat amb columnes com Data, Hora, Temperatura,
      Irradiància solar global, Precipitació, Evapotranspiració de referència.

Exemple:
    python agropolis_controller.py --meteo-xls "C:/Users/blanc/Downloads/Viladecans - les Filipines - estacio.xls" --crop lettuce
"""

from __future__ import annotations

import argparse
import importlib
import math
import os
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PACKAGE_ROOT / "vendor"

for local_dep in ("vendor_xlrd", "vendor_xlrd_clean"):
    dep_path = VENDOR_ROOT / local_dep
    if dep_path.exists():
        sys.path.insert(0, str(dep_path))

LOCAL_PVLIB = VENDOR_ROOT / "vendor_pvlib"
if LOCAL_PVLIB.exists():
    sys.path.insert(0, str(LOCAL_PVLIB))

LOCAL_BIFACIAL = VENDOR_ROOT / "vendor_bifacial_radiance"
if LOCAL_BIFACIAL.exists():
    sys.path.append(str(LOCAL_BIFACIAL))

LOCAL_RADIANCE_BIN = LOCAL_BIFACIAL / "pyradiance" / "bin"
if LOCAL_RADIANCE_BIN.exists():
    os.environ["PATH"] = str(LOCAL_RADIANCE_BIN) + os.pathsep + os.environ.get("PATH", "")

_PVLIB = None
_BIFACIAL_RADIANCE = None
MODEL_VERSION = "samo_controller_robust_v2_2026-05-06"


def get_pvlib():
    """Return pvlib if installed; otherwise keep the controller runnable."""
    global _PVLIB
    if _PVLIB is not None:
        return _PVLIB or None
    try:
        _PVLIB = importlib.import_module("pvlib")
    except ImportError:
        _PVLIB = False
    return _PVLIB or None


def get_bifacial_radiance():
    """Return bifacial_radiance if installed; RADIANCE executables are checked separately."""
    global _BIFACIAL_RADIANCE
    if _BIFACIAL_RADIANCE is not None:
        return _BIFACIAL_RADIANCE or None
    try:
        _BIFACIAL_RADIANCE = importlib.import_module("bifacial_radiance")
    except ImportError:
        _BIFACIAL_RADIANCE = False
    return _BIFACIAL_RADIANCE or None


def radiance_status() -> dict[str, bool | str]:
    """Check whether the external RADIANCE ray-tracing executables are callable."""
    executables = {name: shutil.which(name) for name in ("oconv", "rtrace", "gendaylit")}
    return {
        "bifacial_radiance_python": get_bifacial_radiance() is not None,
        "radiance_executables": all(executables.values()),
        "oconv": executables["oconv"] or "",
        "rtrace": executables["rtrace"] or "",
        "gendaylit": executables["gendaylit"] or "",
    }


@dataclass(frozen=True)
class SiteConfig:
    latitude: float = 41.287889
    longitude: float = 2.043944
    timezone: str = "Europe/Madrid"
    axis_azimuth_deg: float = 0.0  # files N-S, rotació E-W
    pitch_m: float = 4.20
    gcr: float = 0.417
    albedo: float = 0.20
    module_transparency: float = 0.40
    bifacial_gain: float = 0.03
    max_angle_deg: float = 55.0
    max_step_deg: float = 15.0
    caution_wind_ms: float = 7.0
    stow_wind_ms: float = 10.0


@dataclass(frozen=True)
class ObjectiveWeights:
    energy: float = 0.50
    crop: float = 0.35
    movement: float = 0.15


@dataclass(frozen=True)
class CropStage:
    name: str
    months: tuple[int, ...]
    cycle_start_day: int
    cycle_end_day: int
    temp_opt_low: float
    temp_opt_high: float
    temp_abs_low: float
    temp_abs_high: float
    dli_min: float
    dli_opt: float
    water_sensitivity: float = 1.0
    heat_light_sensitivity: float = 1.0
    productive: bool = True
    stage_penalty: float = 0.0
    kc: float = 1.0


@dataclass(frozen=True)
class CropConfig:
    name: str
    temp_opt_low: float
    temp_opt_high: float
    temp_abs_low: float
    temp_abs_high: float
    dli_min: float
    dli_opt: float
    cycle_days: int
    planting_windows: tuple[str, ...] = ()
    prefers_shade_when_hot: bool = True
    stages: tuple[CropStage, ...] = ()


CROPS: dict[str, CropConfig] = {
    "lettuce": CropConfig(
        "lettuce", 12, 22, 4, 32, 12, 17, 60, ("autumn_winter", "spring"),
        stages=(
            CropStage("establishment", (11, 12, 1, 2, 3, 4, 5, 9, 10), 0, 14, 10, 20, 2, 28, 10, 14, 0.8, 0.6),
            CropStage("leaf_expansion", (11, 12, 1, 2, 3, 4, 5, 9, 10), 15, 45, 12, 22, 4, 30, 12, 17, 1.0, 0.9),
            CropStage("harvest_window", (11, 12, 1, 2, 3, 4, 5, 9, 10), 46, 75, 12, 22, 4, 30, 12, 17, 0.9, 0.9),
            CropStage("summer_offseason_heat_risk", (6, 7, 8), 0, 75, 12, 20, 6, 30, 8, 12, 1.2, 1.6, False, 0.35),
        ),
    ),
    "tomato": CropConfig(
        "tomato", 18, 28, 8, 38, 20, 30, 150, ("spring_summer",),
        stages=(
            CropStage("winter_offseason", (11, 12, 1, 2), 0, 180, 12, 22, 6, 30, 10, 16, 0.8, 0.7, False, 0.30),
            CropStage("establishment", (3, 4), 0, 25, 18, 26, 10, 34, 16, 22, 0.9, 0.8),
            CropStage("vegetative", (4, 5), 26, 55, 18, 28, 12, 36, 20, 28, 1.0, 1.0),
            CropStage("flowering_fruiting", (5, 6, 7, 8), 56, 125, 18, 28, 12, 36, 22, 30, 1.2, 1.1),
            CropStage("late_crop", (9, 10), 126, 180, 16, 26, 8, 32, 16, 24, 1.0, 0.8),
        ),
    ),
    "fava": CropConfig(
        "fava", 10, 22, 2, 32, 15, 22, 150, ("autumn_spring",),
        stages=(
            CropStage("establishment", (10, 11, 12), 0, 30, 8, 20, 0, 28, 8, 14, 0.9, 0.5),
            CropStage("winter_vegetative", (11, 12, 1, 2), 31, 95, 8, 20, 0, 28, 10, 16, 0.9, 0.6),
            CropStage("flowering_pods", (3, 4, 5), 96, 160, 15, 20, 4, 27, 15, 22, 1.3, 1.2),
            CropStage("summer_offseason_heat_risk", (6, 7, 8, 9), 0, 180, 10, 20, 2, 27, 8, 14, 1.1, 1.5, False, 0.30),
        ),
    ),
    "onion": CropConfig(
        "onion", 13, 25, 4, 35, 14, 22, 180, ("autumn_summer",),
        stages=(
            CropStage("initial_establishment", (10, 11, 12, 1), 0, 45, 12, 20, 2, 30, 10, 15, 1.1, 0.7),
            CropStage("vegetative_growth", (1, 2, 3), 46, 110, 13, 24, 4, 32, 14, 20, 1.2, 0.8),
            CropStage("bulbing", (4, 5, 6), 111, 165, 15, 25, 4, 34, 16, 22, 1.2, 0.9),
            CropStage("ripening_drydown", (6, 7), 166, 210, 18, 28, 8, 35, 12, 20, 0.6, 0.8),
            CropStage("late_summer_offseason", (8, 9), 0, 210, 13, 25, 4, 35, 8, 14, 0.8, 1.0, False, 0.25),
        ),
    ),
}


CATALAN_COLUMN_MAP = {
    "Data": "date",
    "Hora": "time",
    "Temperatura": "air_temp_c",
    "Temperatura màxima": "air_temp_max_c",
    "Temperatura mínima": "air_temp_min_c",
    "Temperatura de subsol a 5 cm": "soil_temp_c",
    "Temperatura de subsol a 50 cm": "deep_soil_temp_c",
    "Velocitat escalar del vent a 2m": "wind_speed_ms",
    "Humitat relativa": "relative_humidity_pct",
    "Humitat relativa màxima": "relative_humidity_max_pct",
    "Humitat relativa mínima": "relative_humidity_min_pct",
    "Precipitació": "precipitation_mm",
    "Irradiància solar global": "ghi_wm2",
    "Evapotranspiració de referència": "eto_mm",
}


def load_meteocat(path: Path) -> pd.DataFrame:
    """Llegeix CSV/XLS Meteocat i retorna un DataFrame horari normalitzat."""
    if path.suffix.lower() in {".xls", ".xlsx"}:
        data = pd.read_excel(path)
    else:
        data = pd.read_csv(path)

    data = data.rename(columns={k: v for k, v in CATALAN_COLUMN_MAP.items() if k in data.columns})
    required = {"date", "time", "air_temp_c", "ghi_wm2"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Falten columnes obligatòries: {sorted(missing)}")

    data = data.replace("--", np.nan)
    for col in data.columns:
        if col not in {"date", "time"}:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    date_text = data["date"].astype(str).str.strip()
    time_text = data["time"].astype(str).str.strip()
    is_24 = time_text.str.startswith("24:")
    fixed_time = time_text.mask(is_24, time_text.str.replace("24:", "00:", regex=False))
    timestamp_utc = pd.to_datetime(date_text + " " + fixed_time, dayfirst=True, errors="coerce")
    timestamp_utc = timestamp_utc + pd.to_timedelta(is_24.astype(int), unit="D")
    timestamp_utc = timestamp_utc.dt.tz_localize("UTC")
    timestamp_local = timestamp_utc.dt.tz_convert("Europe/Madrid").dt.tz_localize(None)
    data.insert(0, "timestamp_utc", timestamp_utc)
    data.insert(0, "timestamp", timestamp_local)
    data = data.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    defaults = {
        "wind_speed_ms": 0.0,
        "relative_humidity_pct": 70.0,
        "soil_temp_c": data["air_temp_c"],
        "precipitation_mm": 0.0,
        "eto_mm": 0.0,
    }
    for col, value in defaults.items():
        if col not in data.columns:
            data[col] = value
        data[col] = data[col].ffill().bfill().fillna(value if np.isscalar(value) else 0)

    data["ghi_wm2"] = data["ghi_wm2"].clip(lower=0).fillna(0)
    return data


def localized_index(times: pd.Series, timezone: str) -> pd.DatetimeIndex:
    """Normalize local Meteocat timestamps to a timezone-aware index."""
    index = pd.DatetimeIndex(pd.to_datetime(times))
    if index.tz is None:
        return index.tz_localize(timezone, nonexistent="shift_forward", ambiguous="NaT")
    return index.tz_convert(timezone)


def solar_position(times: pd.Series, site: SiteConfig) -> pd.DataFrame:
    """Solar position in Viladecans; pvlib/NREL SPA if available, NOAA fallback."""
    pvlib = get_pvlib()
    if pvlib is not None:
        local_index = localized_index(times, site.timezone)
        solpos = pvlib.solarposition.get_solarposition(
            local_index,
            site.latitude,
            site.longitude,
            method="nrel_numpy",
        )
        zenith = solpos["zenith"].to_numpy(float)
        elevation = solpos["elevation"].to_numpy(float)
        azimuth = solpos["azimuth"].to_numpy(float)
        az_rad = np.deg2rad(azimuth)
        el_rad = np.deg2rad(elevation)
        east = np.cos(el_rad) * np.sin(az_rad)
        north = np.cos(el_rad) * np.cos(az_rad)
        up = np.sin(el_rad)
        return pd.DataFrame(
            {
                "solar_elevation_deg": elevation,
                "solar_zenith_deg": zenith,
                "solar_azimuth_deg": azimuth,
                "sun_east": east,
                "sun_north": north,
                "sun_up": up,
                "cos_zenith": np.maximum(np.cos(np.deg2rad(zenith)), 0),
                "solar_model": "pvlib_nrel_spa",
            }
        )

    local = pd.to_datetime(times)
    day = local.dt.dayofyear.to_numpy()
    hour = (
        local.dt.hour.to_numpy()
        + local.dt.minute.to_numpy() / 60
        + local.dt.second.to_numpy() / 3600
    )

    gamma = 2 * np.pi / 365 * (day - 1 + (hour - 12) / 24)
    decl = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.00148 * np.sin(3 * gamma)
    )
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )

    # Europe/Madrid: CET/CEST. Per control real, passar timestamps amb timezone.
    utc_offset = np.where((local.dt.month >= 4) & (local.dt.month <= 10), 2, 1)
    true_solar_time = (hour * 60 + eq_time + 4 * site.longitude - 60 * utc_offset) % 1440
    hour_angle = np.deg2rad(true_solar_time / 4 - 180)
    lat = math.radians(site.latitude)

    cos_zenith = (
        math.sin(lat) * np.sin(decl)
        + math.cos(lat) * np.cos(decl) * np.cos(hour_angle)
    )
    cos_zenith = np.clip(cos_zenith, -1, 1)
    zenith = np.rad2deg(np.arccos(cos_zenith))
    elevation = 90 - zenith

    # Vector solar ENU: east, north, up.
    east = -np.cos(decl) * np.sin(hour_angle)
    north = math.cos(lat) * np.sin(decl) - math.sin(lat) * np.cos(decl) * np.cos(hour_angle)
    up = cos_zenith
    azimuth = (np.rad2deg(np.arctan2(east, north)) + 360) % 360

    return pd.DataFrame(
        {
            "solar_elevation_deg": elevation,
            "solar_zenith_deg": zenith,
            "solar_azimuth_deg": azimuth,
            "sun_east": east,
            "sun_north": north,
            "sun_up": up,
            "cos_zenith": np.maximum(up, 0),
            "solar_model": "noaa_fallback",
        }
    )


def erbs_decomposition(
    ghi: np.ndarray,
    cos_zenith: np.ndarray,
    day_of_year: np.ndarray,
    zenith_deg: np.ndarray | None = None,
    times: pd.Series | pd.DatetimeIndex | None = None,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Split GHI into DHI/DNI; use pvlib Erbs when available."""
    pvlib = get_pvlib()
    if pvlib is not None and zenith_deg is not None:
        datetime_or_doy = localized_index(pd.Series(times), "Europe/Madrid") if times is not None else day_of_year
        data = pvlib.irradiance.erbs(ghi, zenith_deg, datetime_or_doy)
        return (
            np.asarray(data["dhi"], dtype=float).clip(min=0),
            np.asarray(data["dni"], dtype=float).clip(min=0),
            "pvlib_erbs",
        )

    solar_constant = 1367.0
    eccentricity = 1 + 0.033 * np.cos(2 * np.pi * day_of_year / 365)
    extraterrestrial_horizontal = solar_constant * eccentricity * np.maximum(cos_zenith, 0)
    kt = np.divide(ghi, extraterrestrial_horizontal, out=np.zeros_like(ghi), where=extraterrestrial_horizontal > 0)
    kt = np.clip(kt, 0, 1.2)

    diffuse_fraction = np.where(
        kt <= 0.22,
        1 - 0.09 * kt,
        np.where(
            kt <= 0.80,
            0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4,
            0.165,
        ),
    )
    diffuse_fraction = np.clip(diffuse_fraction, 0.05, 1.0)
    dhi = ghi * diffuse_fraction
    dni = np.divide(ghi - dhi, np.maximum(cos_zenith, 0.05), out=np.zeros_like(ghi), where=cos_zenith > 0)
    return dhi.clip(min=0), dni.clip(min=0), "manual_erbs"


def panel_normal(angle_deg: float) -> np.ndarray:
    """Normal del panell per tracker N-S. Angle positiu inclina cap a l'oest."""
    theta = math.radians(angle_deg)
    return np.array([-math.sin(theta), 0.0, math.cos(theta)])


def surface_from_tracker_angle(angle_deg: float, site: SiteConfig) -> tuple[float, float]:
    """Convert tracker angle to surface tilt/azimuth for pvlib transposition."""
    tilt = abs(angle_deg)
    if abs(angle_deg) < 1e-9:
        return 0.0, (site.axis_azimuth_deg + 90) % 360
    azimuth = 270.0 if angle_deg > 0 else 90.0
    return tilt, azimuth


def poa_irradiance(angle_deg: float, row: pd.Series | dict, site: SiteConfig) -> float:
    """Irradiància al pla del panell per un angle candidat."""
    pvlib = get_pvlib()
    if pvlib is not None:
        tilt, azimuth = surface_from_tracker_angle(angle_deg, site)
        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=row["solar_zenith_deg"],
            solar_azimuth=row["solar_azimuth_deg"],
            dni=row["dni_wm2"],
            ghi=row["ghi_wm2"],
            dhi=row["dhi_wm2"],
            albedo=site.albedo,
            model="isotropic",
        )
        return max(0.0, float(poa["poa_global"]) * (1 + site.bifacial_gain))

    normal = panel_normal(angle_deg)
    sun = np.array([row["sun_east"], row["sun_north"], row["sun_up"]])
    cos_incidence = max(float(np.dot(normal, sun)), 0.0)
    tilt_rad = math.radians(abs(angle_deg))
    direct = row["dni_wm2"] * cos_incidence
    diffuse = row["dhi_wm2"] * (1 + math.cos(tilt_rad)) / 2
    ground = site.albedo * row["ghi_wm2"] * (1 - math.cos(tilt_rad)) / 2
    return max(0.0, (direct + diffuse + ground) * (1 + site.bifacial_gain))


def crop_irradiance(angle_deg: float, row: pd.Series | dict, site: SiteConfig) -> float:
    """Llum que arriba al cultiu sota el tracker amb ombra paramètrica."""
    if row["sun_up"] <= 0 or row["ghi_wm2"] <= 0:
        return 0.0
    normal = panel_normal(angle_deg)
    sun = np.array([row["sun_east"], row["sun_north"], row["sun_up"]])
    intercept = max(float(np.dot(normal, sun)), 0.0)
    intercept_ratio = np.clip(intercept / max(row["cos_zenith"], 0.08), 0, 1.6)
    beam_horizontal = max(row["ghi_wm2"] - row["dhi_wm2"], 0.0)

    shade_fraction = np.clip(site.gcr * intercept_ratio, 0, 0.90)
    opaque = 1 - site.module_transparency
    beam_to_crop = beam_horizontal * (1 - shade_fraction * opaque)
    diffuse_to_crop = row["dhi_wm2"] * (1 - 0.45 * site.gcr * opaque)
    return max(0.0, beam_to_crop + diffuse_to_crop)


def trapezoid_stress(value: float, opt_low: float, opt_high: float, abs_low: float, abs_high: float) -> float:
    """0 dins del rang òptim, 1 fora del rang absolut."""
    if opt_low <= value <= opt_high:
        return 0.0
    if value < opt_low:
        return float(np.clip((opt_low - value) / max(opt_low - abs_low, 1e-6), 0, 1))
    return float(np.clip((value - opt_high) / max(abs_high - opt_high, 1e-6), 0, 1))


def daily_light_integral(crop_wm2: pd.Series) -> pd.Series:
    """Converteix irradiància horària al cultiu en DLI aproximat mol/m2/dia."""
    hourly_mol = crop_wm2 * 2.04 * 3600 / 1_000_000
    return hourly_mol.groupby(crop_wm2.index.date).transform("sum")


def hourly_mol_from_wm2(wm2: float) -> float:
    return float(max(wm2, 0.0) * 2.04 * 3600 / 1_000_000)


def crop_stage_kc(stage: CropStage) -> float:
    if stage.kc != 1.0:
        return stage.kc
    name = stage.name
    if any(token in name for token in ("establishment", "initial")):
        return 0.45
    if any(token in name for token in ("vegetative", "leaf_expansion")):
        return 0.75
    if any(token in name for token in ("flowering", "bulbing", "fruiting", "pods")):
        return 1.05
    if any(token in name for token in ("harvest", "late", "ripening")):
        return 0.85
    if not stage.productive:
        return 0.35
    return 0.90


def planting_date_for_cycle(crop: CropConfig, timestamp: pd.Timestamp | str) -> pd.Timestamp:
    date = pd.Timestamp(timestamp).normalize()
    year = date.year
    if crop.name == "lettuce":
        starts = [pd.Timestamp(year=year, month=m, day=1) for m in (1, 3, 5, 9, 11)]
    elif crop.name == "tomato":
        starts = [pd.Timestamp(year=year - 1, month=3, day=15), pd.Timestamp(year=year, month=3, day=15)]
    elif crop.name == "fava":
        starts = [pd.Timestamp(year=year - 1, month=10, day=15), pd.Timestamp(year=year, month=10, day=15)]
    elif crop.name == "onion":
        starts = [pd.Timestamp(year=year - 1, month=10, day=1), pd.Timestamp(year=year, month=10, day=1)]
    else:
        starts = [pd.Timestamp(year=year, month=1, day=1)]
    valid = [start for start in starts if start <= date]
    return max(valid) if valid else min(starts)


def crop_cycle_day(crop: CropConfig, timestamp: pd.Timestamp | str) -> int:
    start = planting_date_for_cycle(crop, timestamp)
    return max(0, int((pd.Timestamp(timestamp).normalize() - start).days) + 1)


def crop_days_to_planting(crop: CropConfig, timestamp: pd.Timestamp | str) -> int:
    start = planting_date_for_cycle(crop, timestamp)
    return max(0, int((start - pd.Timestamp(timestamp).normalize()).days))


def crop_cycle_progress(crop: CropConfig, timestamp: pd.Timestamp | str) -> float:
    return float(np.clip(crop_cycle_day(crop, timestamp) / max(crop.cycle_days, 1), 0, 1.0))


def crop_stage(crop: CropConfig, timestamp: pd.Timestamp | str) -> CropStage:
    month = pd.Timestamp(timestamp).month
    cycle_day = crop_cycle_day(crop, timestamp)
    offseason_names = {
        "lettuce": "summer_offseason_heat_risk",
        "tomato": "winter_offseason",
        "fava": "summer_offseason_heat_risk",
        "onion": "late_summer_offseason",
    }
    if crop.name == "lettuce" and month in (6, 7, 8):
        return next(stage for stage in crop.stages if stage.name == "summer_offseason_heat_risk")
    if crop.name == "tomato" and month in (11, 12, 1, 2):
        return next(stage for stage in crop.stages if stage.name == "winter_offseason")
    if crop.name == "fava" and month in (6, 7, 8, 9):
        return next(stage for stage in crop.stages if stage.name == "summer_offseason_heat_risk")
    if crop.name == "onion" and month in (8, 9):
        return next(stage for stage in crop.stages if stage.name == "late_summer_offseason")
    for stage in crop.stages:
        if stage.productive and stage.cycle_start_day <= cycle_day <= stage.cycle_end_day:
            return stage
    if cycle_day > crop.cycle_days:
        return CropStage(
            "post_harvest_or_out_of_cycle",
            tuple(range(1, 13)),
            crop.cycle_days + 1,
            999,
            crop.temp_opt_low,
            crop.temp_opt_high,
            crop.temp_abs_low,
            crop.temp_abs_high,
            crop.dli_min * 0.6,
            crop.dli_opt * 0.6,
            productive=False,
            stage_penalty=0.35,
            kc=0.35,
        )
    if offseason_names.get(crop.name):
        for stage in crop.stages:
            if stage.name == offseason_names[crop.name]:
                return stage
    return CropStage(
        "default",
        tuple(range(1, 13)),
        0,
        crop.cycle_days,
        crop.temp_opt_low,
        crop.temp_opt_high,
        crop.temp_abs_low,
        crop.temp_abs_high,
        crop.dli_min,
        crop.dli_opt,
    )


def crop_stress_components(row: pd.Series | dict, crop: CropConfig) -> dict[str, float]:
    stage = crop_stage(crop, row["timestamp"])
    temp = trapezoid_stress(row["air_temp_c"], stage.temp_opt_low, stage.temp_opt_high, stage.temp_abs_low, stage.temp_abs_high)
    soil = trapezoid_stress(row["soil_temp_c"], stage.temp_opt_low - 2, stage.temp_opt_high + 2, stage.temp_abs_low, stage.temp_abs_high)
    heat_light = 1.0 if row["air_temp_c"] > stage.temp_opt_high and row["ghi_wm2"] > 650 else 0.0
    kc = crop_stage_kc(stage)
    etc = max(0.0, float(row["eto_mm"]) * kc)
    water = float(np.clip((etc - float(row["precipitation_mm"])) / max(etc, 0.7), 0, 1))
    stage_component = float(np.clip(stage.stage_penalty, 0, 1))
    total = float(np.clip(
        0.32 * temp
        + 0.18 * soil
        + 0.24 * water * stage.water_sensitivity
        + 0.18 * heat_light * stage.heat_light_sensitivity
        + stage_component,
        0,
        1,
    ))
    return {
        "temp_air_stress": float(np.clip(temp, 0, 1)),
        "temp_soil_stress": float(np.clip(soil, 0, 1)),
        "water_stress": float(np.clip(water * stage.water_sensitivity, 0, 1)),
        "heat_light_stress": float(np.clip(heat_light * stage.heat_light_sensitivity, 0, 1)),
        "stage_stress": stage_component,
        "crop_stress": total,
        "crop_kc": float(kc),
        "etc_mm": float(etc),
    }


def base_crop_stress(row: pd.Series | dict, crop: CropConfig) -> float:
    return crop_stress_components(row, crop)["crop_stress"]


def crop_score_components(angle_deg: float, row: pd.Series | dict, site: SiteConfig, crop: CropConfig) -> dict[str, float]:
    stage = crop_stage(crop, row["timestamp"])
    crop_wm2 = crop_irradiance(angle_deg, row, site)
    dli_candidate = float(row["dli_reference_mol"] - row.get("ghi_mol_hour", hourly_mol_from_wm2(row["ghi_wm2"])) + hourly_mol_from_wm2(crop_wm2))
    light_deficit = max(stage.dli_min - dli_candidate, 0) / max(stage.dli_min, 1e-9)
    excess_light = 1.0 if crop_wm2 > 650 and row["air_temp_c"] > stage.temp_opt_high else 0.0
    stress_parts = crop_stress_components(row, crop)
    stress = stress_parts["crop_stress"]

    # Si el cultiu està estressat per calor/radiació, l'ombra útil puja el score.
    protection = np.clip((row["ghi_wm2"] - crop_wm2) / max(row["ghi_wm2"], 1), 0, 1)
    score = 1 - stress
    score += 0.35 * stress * protection
    score -= 0.55 * light_deficit
    score -= 0.20 * excess_light
    return {
        **stress_parts,
        "crop_score": float(np.clip(score, 0, 1)),
        "crop_irradiance_wm2": float(crop_wm2),
        "dli_candidate_mol": float(max(dli_candidate, 0)),
        "light_deficit_stress": float(np.clip(light_deficit, 0, 1)),
        "excess_light_stress": float(excess_light),
        "shade_protection_score": float(protection),
    }


def crop_score(angle_deg: float, row: pd.Series | dict, site: SiteConfig, crop: CropConfig) -> tuple[float, float]:
    parts = crop_score_components(angle_deg, row, site, crop)
    return parts["crop_score"], parts["crop_irradiance_wm2"]


def prepare_physics_data(meteo: pd.DataFrame, site: SiteConfig) -> pd.DataFrame:
    """Add solar position, irradiance components and reference DLI to meteo data."""
    solar = solar_position(meteo["timestamp"], site)
    data = pd.concat([meteo.reset_index(drop=True), solar], axis=1)
    day = data["timestamp"].dt.dayofyear.to_numpy()
    dhi, dni, decomposition_model = erbs_decomposition(
        data["ghi_wm2"].to_numpy(float),
        data["cos_zenith"].to_numpy(float),
        day,
        data["solar_zenith_deg"].to_numpy(float),
        data["timestamp"],
    )
    data["dhi_wm2"] = dhi
    data["dni_wm2"] = dni
    data["irradiance_decomposition_model"] = decomposition_model
    data = data.set_index("timestamp", drop=False)
    data["dli_reference_mol"] = daily_light_integral(data["ghi_wm2"])
    data["ghi_mol_hour"] = data["ghi_wm2"].map(hourly_mol_from_wm2)
    return data


def allowed_angles(current_angle: float, reference_angle: float, site: SiteConfig, step_deg: float) -> list[float]:
    raw = np.arange(-site.max_angle_deg, site.max_angle_deg + 0.001, step_deg)
    limited = raw[np.abs(raw - current_angle) <= site.max_step_deg + 1e-9]
    lower = max(-site.max_angle_deg, current_angle - site.max_step_deg)
    upper = min(site.max_angle_deg, current_angle + site.max_step_deg)
    extra = np.array([lower, upper, np.clip(reference_angle, lower, upper), current_angle])
    limited = np.unique(np.round(np.concatenate([limited, extra]), 3))
    if len(limited) == 0:
        target = np.clip(current_angle, -site.max_angle_deg, site.max_angle_deg)
        limited = np.array([target])
    return [float(round(x, 3)) for x in sorted(limited, key=lambda x: (abs(x - reference_angle), abs(x - current_angle)))]


def reference_tracker_angle(row: pd.Series | dict, site: SiteConfig) -> float:
    """Energy-only single-axis reference angle with backtracking when pvlib exists."""
    pvlib = get_pvlib()
    if row["solar_elevation_deg"] <= 0:
        return 0.0
    if pvlib is not None:
        tracking = pvlib.tracking.singleaxis(
            apparent_zenith=row["solar_zenith_deg"],
            solar_azimuth=row["solar_azimuth_deg"],
            axis_tilt=0,
            axis_azimuth=site.axis_azimuth_deg,
            max_angle=site.max_angle_deg,
            backtrack=True,
            gcr=site.gcr,
        )
        theta = tracking["tracker_theta"]
        if hasattr(theta, "iloc"):
            theta = theta.iloc[0]
        if np.ndim(theta) > 0:
            theta = np.asarray(theta, dtype=float).ravel()[0]
        theta = float(theta)
        if np.isnan(theta):
            return 0.0
        return -theta

    # Fallback: project sun on the east-west rotation plane.
    theta = math.degrees(math.atan2(row["sun_east"], max(row["sun_up"], 1e-9)))
    return float(np.clip(theta, -site.max_angle_deg, site.max_angle_deg))


def recommend_for_row(
    row: pd.Series,
    current_angle: float,
    site: SiteConfig,
    crop: CropConfig,
    weights: ObjectiveWeights,
    step_deg: float,
) -> dict:
    stage = crop_stage(crop, row["timestamp"])
    stress_parts = crop_stress_components(row, crop)
    tracker_ref = reference_tracker_angle(row, site)
    ref_poa = poa_irradiance(tracker_ref, row, site) if row["solar_elevation_deg"] > 0 else 0.0
    ref_crop_parts = crop_score_components(tracker_ref, row, site, crop) if row["solar_elevation_deg"] > 0 else crop_score_components(0.0, row, site, crop)

    def common(extra: dict) -> dict:
        return {
            "tracker_reference_angle_deg": tracker_ref,
            "reference_poa_wm2": float(ref_poa),
            "reference_crop_irradiance_wm2": float(ref_crop_parts["crop_irradiance_wm2"]),
            "reference_crop_score": float(ref_crop_parts["crop_score"]),
            "crop_stage": stage.name,
            "crop_cycle_day": crop_cycle_day(crop, row["timestamp"]),
            "crop_cycle_progress": crop_cycle_progress(crop, row["timestamp"]),
            "crop_days_to_planting": crop_days_to_planting(crop, row["timestamp"]),
            "crop_cycle_days_expected": crop.cycle_days,
            "planting_date": planting_date_for_cycle(crop, row["timestamp"]).date().isoformat(),
            "harvest_date": (planting_date_for_cycle(crop, row["timestamp"]) + pd.Timedelta(days=crop.cycle_days - 1)).date().isoformat(),
            "crop_stage_productive": stage.productive,
            "crop_stage_penalty": stage.stage_penalty,
            **stress_parts,
            **extra,
        }

    if row["wind_speed_ms"] >= site.stow_wind_ms:
        rec_poa = 0.0
        crop_parts = crop_score_components(0.0, row, site, crop)
        return common({
            "recommended_angle_deg": 0.0,
            "final_score": 0.0,
            "energy_score": 0.0,
            "crop_score": float(crop_parts["crop_score"]),
            "movement_penalty": abs(current_angle) / (2 * site.max_angle_deg),
            "poa_wm2": rec_poa,
            "crop_irradiance_wm2": float(crop_parts["crop_irradiance_wm2"]),
            "angle_delta_vs_tracker_deg": -tracker_ref,
            "energy_loss_vs_tracker_pct": 0.0 if ref_poa <= 0 else float(np.clip((ref_poa - rec_poa) / ref_poa * 100, -100, 100)),
            "crop_light_delta_vs_tracker_pct": 0.0 if ref_crop_parts["crop_irradiance_wm2"] <= 0 else float((crop_parts["crop_irradiance_wm2"] - ref_crop_parts["crop_irradiance_wm2"]) / ref_crop_parts["crop_irradiance_wm2"] * 100),
            "effective_energy_weight": weights.energy,
            "effective_crop_weight": weights.crop,
            "effective_movement_weight": weights.movement,
            **{k: crop_parts[k] for k in ("dli_candidate_mol", "light_deficit_stress", "excess_light_stress", "shade_protection_score")},
            "reason": "wind_stow",
        })

    if row["ghi_wm2"] < 20 or row["solar_elevation_deg"] <= 0:
        step_to_zero = float(np.clip(-current_angle, -site.max_step_deg, site.max_step_deg))
        rest_angle = float(np.clip(current_angle + step_to_zero, -site.max_angle_deg, site.max_angle_deg))
        crop_parts = crop_score_components(rest_angle, row, site, crop)
        return common({
            "recommended_angle_deg": rest_angle,
            "final_score": 0.0,
            "energy_score": 0.0,
            "crop_score": float(crop_parts["crop_score"]),
            "movement_penalty": abs(rest_angle - current_angle) / (2 * site.max_angle_deg),
            "poa_wm2": 0.0,
            "crop_irradiance_wm2": float(crop_parts["crop_irradiance_wm2"]),
            "angle_delta_vs_tracker_deg": rest_angle - tracker_ref,
            "energy_loss_vs_tracker_pct": 0.0,
            "crop_light_delta_vs_tracker_pct": 0.0,
            "effective_energy_weight": weights.energy,
            "effective_crop_weight": weights.crop,
            "effective_movement_weight": weights.movement,
            **{k: crop_parts[k] for k in ("dli_candidate_mol", "light_deficit_stress", "excess_light_stress", "shade_protection_score")},
            "reason": "night_idle",
        })

    candidates = allowed_angles(current_angle, tracker_ref, site, step_deg)
    poas = np.array([poa_irradiance(a, row, site) for a in candidates])
    poa_norm = poas / max(float(ref_poa), float(np.nanmax(poas)), 1.0)

    best = None
    for angle, poa, energy_norm in zip(candidates, poas, poa_norm):
        crop_parts = crop_score_components(angle, row, site, crop)
        crop_norm = crop_parts["crop_score"]
        crop_wm2 = crop_parts["crop_irradiance_wm2"]
        movement = abs(angle - current_angle) / (2 * site.max_angle_deg)
        extreme_angle = abs(angle) / max(site.max_angle_deg, 1e-9)

        dynamic_crop_weight = weights.crop
        dynamic_energy_weight = weights.energy
        dynamic_movement_weight = weights.movement
        if stress_parts["crop_stress"] > 0.45:
            dynamic_crop_weight += 0.15
            dynamic_energy_weight -= 0.15
        if site.caution_wind_ms <= row["wind_speed_ms"] < site.stow_wind_ms:
            dynamic_movement_weight += 0.12
            movement += 0.45 * extreme_angle

        final = dynamic_energy_weight * energy_norm + dynamic_crop_weight * crop_norm - dynamic_movement_weight * movement
        energy_loss = 0.0 if ref_poa <= 0 else float(np.clip((ref_poa - poa) / ref_poa * 100, -100, 100))
        crop_light_delta = 0.0 if ref_crop_parts["crop_irradiance_wm2"] <= 0 else float((crop_wm2 - ref_crop_parts["crop_irradiance_wm2"]) / ref_crop_parts["crop_irradiance_wm2"] * 100)
        item = common({
            "recommended_angle_deg": angle,
            "final_score": float(final),
            "energy_score": float(energy_norm),
            "crop_score": float(crop_norm),
            "movement_penalty": float(movement),
            "poa_wm2": float(poa),
            "crop_irradiance_wm2": float(crop_wm2),
            "angle_delta_vs_tracker_deg": float(angle - tracker_ref),
            "energy_loss_vs_tracker_pct": energy_loss,
            "crop_light_delta_vs_tracker_pct": crop_light_delta,
            "effective_energy_weight": float(dynamic_energy_weight),
            "effective_crop_weight": float(dynamic_crop_weight),
            "effective_movement_weight": float(dynamic_movement_weight),
            **{k: crop_parts[k] for k in ("dli_candidate_mol", "light_deficit_stress", "excess_light_stress", "shade_protection_score")},
            "reason": "wind_caution" if site.caution_wind_ms <= row["wind_speed_ms"] < site.stow_wind_ms else "optimized",
        })
        if best is None or item["final_score"] > best["final_score"]:
            best = item
    return best or {}


def ground_irradiance_profile(angle_deg: float, row: pd.Series | dict, site: SiteConfig, sensors: int = 9) -> dict:
    """Parametric ground scan shaped like a RADIANCE groundAnalysis output."""
    if row["sun_up"] <= 0 or row["ghi_wm2"] <= 0:
        values = np.zeros(sensors)
    else:
        x = np.linspace(-site.pitch_m / 2, site.pitch_m / 2, sensors)
        shadow_center = np.clip(-math.tan(math.radians(angle_deg)) * 0.9, -site.pitch_m / 2, site.pitch_m / 2)
        shadow_width = max(site.pitch_m * site.gcr * (1.1 - 0.4 * site.module_transparency), 0.25)
        shade = np.exp(-0.5 * ((x - shadow_center) / shadow_width) ** 2)
        opaque = 1 - site.module_transparency
        direct_horizontal = max(row["ghi_wm2"] - row["dhi_wm2"], 0.0)
        direct = direct_horizontal * (1 - opaque * np.clip(shade, 0, 0.95))
        diffuse = row["dhi_wm2"] * (1 - 0.35 * site.gcr * opaque)
        values = np.maximum(0, direct + diffuse)

    return {
        "ground_mean_wm2": float(np.mean(values)),
        "ground_p10_wm2": float(np.percentile(values, 10)),
        "ground_p50_wm2": float(np.percentile(values, 50)),
        "ground_p90_wm2": float(np.percentile(values, 90)),
        "ground_uniformity": float(np.min(values) / max(np.mean(values), 1e-9)),
    }


def raytrace_engine_label() -> str:
    status = radiance_status()
    if status["bifacial_radiance_python"] and status["radiance_executables"]:
        return "parametric_ground_scan_radiance_ready"
    if status["bifacial_radiance_python"]:
        return "bifacial_radiance_no_radiance_parametric_fallback"
    return "parametric_fallback"


def build_raytrace_dataset(
    meteo: pd.DataFrame,
    site: SiteConfig,
    crops: dict[str, CropConfig],
    angle_step: float = 10.0,
    sensors: int = 9,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Create an hour x angle x crop dataset for ray-tracing/calibration workflows."""
    data = prepare_physics_data(meteo, site).reset_index(drop=True)
    if max_rows is not None:
        data = data.head(max_rows)

    angles = np.arange(-site.max_angle_deg, site.max_angle_deg + 0.001, angle_step)
    engine = raytrace_engine_label()
    status = radiance_status()
    rows = []

    for _, row in data.iterrows():
        tracker_ref = reference_tracker_angle(row, site)
        for angle in angles:
            poa = poa_irradiance(float(angle), row, site)
            ground = ground_irradiance_profile(float(angle), row, site, sensors=sensors)
            for crop_key, crop in crops.items():
                crop_parts = crop_score_components(float(angle), row, site, crop)
                score = crop_parts["crop_score"]
                crop_wm2 = crop_parts["crop_irradiance_wm2"]
                stage = crop_stage(crop, row["timestamp"])
                rows.append(
                    {
                        "model_version": MODEL_VERSION,
                        "timestamp": row["timestamp"],
                        "timestamp_utc": row.get("timestamp_utc", pd.NaT),
                        "crop": crop_key,
                        "crop_stage": stage.name,
                        "crop_cycle_day": crop_cycle_day(crop, row["timestamp"]),
                        "crop_cycle_progress": crop_cycle_progress(crop, row["timestamp"]),
                        "crop_days_to_planting": crop_days_to_planting(crop, row["timestamp"]),
                        "crop_cycle_days_expected": crop.cycle_days,
                        "crop_stage_productive": stage.productive,
                        "crop_stage_penalty": stage.stage_penalty,
                        "planting_date": planting_date_for_cycle(crop, row["timestamp"]).date().isoformat(),
                        "angle_deg": float(angle),
                        "tracker_reference_angle_deg": tracker_ref,
                        "poa_wm2": float(poa),
                        "crop_irradiance_wm2": float(crop_wm2),
                        "crop_score": float(score),
                        "crop_stress": float(crop_parts["crop_stress"]),
                        "temp_air_stress": float(crop_parts["temp_air_stress"]),
                        "temp_soil_stress": float(crop_parts["temp_soil_stress"]),
                        "water_stress": float(crop_parts["water_stress"]),
                        "heat_light_stress": float(crop_parts["heat_light_stress"]),
                        "stage_stress": float(crop_parts["stage_stress"]),
                        "light_deficit_stress": float(crop_parts["light_deficit_stress"]),
                        "excess_light_stress": float(crop_parts["excess_light_stress"]),
                        "shade_protection_score": float(crop_parts["shade_protection_score"]),
                        "dli_candidate_mol": float(crop_parts["dli_candidate_mol"]),
                        "crop_kc": float(crop_parts["crop_kc"]),
                        "etc_mm": float(crop_parts["etc_mm"]),
                        "ghi_wm2": float(row["ghi_wm2"]),
                        "dni_wm2": float(row["dni_wm2"]),
                        "dhi_wm2": float(row["dhi_wm2"]),
                        "solar_elevation_deg": float(row["solar_elevation_deg"]),
                        "solar_zenith_deg": float(row["solar_zenith_deg"]),
                        "solar_azimuth_deg": float(row["solar_azimuth_deg"]),
                        "air_temp_c": float(row["air_temp_c"]),
                        "soil_temp_c": float(row["soil_temp_c"]),
                        "relative_humidity_pct": float(row["relative_humidity_pct"]),
                        "wind_speed_ms": float(row["wind_speed_ms"]),
                        "precipitation_mm": float(row["precipitation_mm"]),
                        "eto_mm": float(row["eto_mm"]),
                        "dli_reference_mol": float(row["dli_reference_mol"]),
                        "ghi_mol_hour": float(row["ghi_mol_hour"]),
                        "module_transparency": site.module_transparency,
                        "pitch_m": site.pitch_m,
                        "gcr": site.gcr,
                        "albedo": site.albedo,
                        "site_latitude": site.latitude,
                        "site_longitude": site.longitude,
                        "angle_sign_convention": "negative_morning_east_positive_afternoon_west",
                        "raytrace_engine": engine,
                        "bifacial_radiance_python": bool(status["bifacial_radiance_python"]),
                        "radiance_executables": bool(status["radiance_executables"]),
                        **ground,
                    }
                )

    return pd.DataFrame(rows)


def run_controller(
    meteo: pd.DataFrame,
    site: SiteConfig,
    crop: CropConfig,
    weights: ObjectiveWeights,
    step_deg: float,
    initial_angle: float,
) -> pd.DataFrame:
    data = prepare_physics_data(meteo, site)

    rows = []
    current_angle = initial_angle
    for _, row in data.iterrows():
        rec = recommend_for_row(row, current_angle, site, crop, weights, step_deg)
        current_angle = rec["recommended_angle_deg"]
        rows.append(rec)

    result = pd.concat([data.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    result["model_version"] = MODEL_VERSION
    result["site_latitude"] = site.latitude
    result["site_longitude"] = site.longitude
    result["angle_sign_convention"] = "negative_morning_east_positive_afternoon_west"
    result["base_energy_weight"] = weights.energy
    result["base_crop_weight"] = weights.crop
    result["base_movement_weight"] = weights.movement
    keep = [
        "model_version",
        "timestamp",
        "timestamp_utc",
        "site_latitude",
        "site_longitude",
        "angle_sign_convention",
        "air_temp_c",
        "soil_temp_c",
        "relative_humidity_pct",
        "wind_speed_ms",
        "precipitation_mm",
        "eto_mm",
        "ghi_wm2",
        "solar_elevation_deg",
        "solar_zenith_deg",
        "solar_azimuth_deg",
        "solar_model",
        "dhi_wm2",
        "dni_wm2",
        "irradiance_decomposition_model",
        "dli_reference_mol",
        "ghi_mol_hour",
        "recommended_angle_deg",
        "tracker_reference_angle_deg",
        "angle_delta_vs_tracker_deg",
        "final_score",
        "energy_score",
        "crop_score",
        "reference_poa_wm2",
        "reference_crop_irradiance_wm2",
        "reference_crop_score",
        "energy_loss_vs_tracker_pct",
        "crop_light_delta_vs_tracker_pct",
        "effective_energy_weight",
        "effective_crop_weight",
        "effective_movement_weight",
        "base_energy_weight",
        "base_crop_weight",
        "base_movement_weight",
        "movement_penalty",
        "poa_wm2",
        "crop_irradiance_wm2",
        "dli_candidate_mol",
        "crop_stress",
        "temp_air_stress",
        "temp_soil_stress",
        "water_stress",
        "heat_light_stress",
        "stage_stress",
        "light_deficit_stress",
        "excess_light_stress",
        "shade_protection_score",
        "crop_kc",
        "etc_mm",
        "crop_stage",
        "crop_cycle_day",
        "crop_cycle_progress",
        "crop_days_to_planting",
        "crop_cycle_days_expected",
        "planting_date",
        "harvest_date",
        "crop_stage_penalty",
        "crop_stage_productive",
        "reason",
    ]
    return result[[c for c in keep if c in result.columns]]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlador agrivoltaic Agròpolis Viladecans")
    parser.add_argument("--meteo-xls", type=Path, required=True, help="Fitxer Meteocat .xls/.xlsx/.csv")
    parser.add_argument("--crop", choices=sorted(CROPS), default="lettuce", help="Cultiu objectiu")
    parser.add_argument("--out", type=Path, default=Path("outputs/control_recommendations.csv"))
    parser.add_argument("--lat", type=float, default=41.287889)
    parser.add_argument("--lon", type=float, default=2.043944)
    parser.add_argument("--transparency", type=float, default=0.40, help="Fracció de llum que deixa passar el mòdul")
    parser.add_argument("--energy-weight", type=float, default=0.50)
    parser.add_argument("--crop-weight", type=float, default=0.35)
    parser.add_argument("--movement-weight", type=float, default=0.15)
    parser.add_argument("--angle-step", type=float, default=5.0)
    parser.add_argument("--initial-angle", type=float, default=0.0)
    parser.add_argument("--start", type=str, default=None, help="Filtra des de data ISO, ex. 2025-07-18")
    parser.add_argument("--end", type=str, default=None, help="Filtra fins data ISO, ex. 2025-07-19")
    parser.add_argument("--generate-raytrace-dataset", action="store_true", help="Genera dataset hora x angle x cultiu")
    parser.add_argument("--raytrace-out", type=Path, default=Path("outputs/raytrace_training_dataset.csv"))
    parser.add_argument("--raytrace-angle-step", type=float, default=10.0)
    parser.add_argument("--raytrace-sensors", type=int, default=9, help="Punts virtuals de ground scan sota/pitch")
    parser.add_argument("--raytrace-max-rows", type=int, default=None, help="Limita files horàries per proves ràpides")
    parser.add_argument("--raytrace-crops", nargs="+", choices=sorted(CROPS), default=sorted(CROPS))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    site = replace(
        SiteConfig(),
        latitude=args.lat,
        longitude=args.lon,
        module_transparency=args.transparency,
    )
    weights = ObjectiveWeights(args.energy_weight, args.crop_weight, args.movement_weight)
    meteo = load_meteocat(args.meteo_xls)

    if args.start:
        meteo = meteo[meteo["timestamp"] >= pd.Timestamp(args.start)]
    if args.end:
        meteo = meteo[meteo["timestamp"] < pd.Timestamp(args.end)]
    if meteo.empty:
        raise ValueError("No hi ha dades després d'aplicar els filtres de data.")

    result = run_controller(meteo, site, CROPS[args.crop], weights, args.angle_step, args.initial_angle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)

    raytrace_output = None
    if args.generate_raytrace_dataset:
        selected_crops = {name: CROPS[name] for name in args.raytrace_crops}
        raytrace = build_raytrace_dataset(
            meteo,
            site,
            selected_crops,
            angle_step=args.raytrace_angle_step,
            sensors=args.raytrace_sensors,
            max_rows=args.raytrace_max_rows,
        )
        args.raytrace_out.parent.mkdir(parents=True, exist_ok=True)
        raytrace.to_csv(args.raytrace_out, index=False)
        raytrace_output = str(args.raytrace_out)

    daylight = result[result["ghi_wm2"] > 20]
    summary = {
        "rows": len(result),
        "daylight_rows": len(daylight),
        "crop": args.crop,
        "mean_angle_daylight": round(float(daylight["recommended_angle_deg"].mean()), 2) if len(daylight) else 0,
        "mean_poa_daylight": round(float(daylight["poa_wm2"].mean()), 2) if len(daylight) else 0,
        "mean_crop_irradiance_daylight": round(float(daylight["crop_irradiance_wm2"].mean()), 2) if len(daylight) else 0,
        "output": str(args.out),
        "raytrace_output": raytrace_output,
        "raytrace_engine": raytrace_engine_label() if args.generate_raytrace_dataset else None,
    }
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
