"""
Energy Consumption Analysis Module.

Analyzes a building's energy signature from hourly consumption + temperature data.
Outputs: UA value, baseload, COP, energy class, benchmarks.
Auto-detects heating system type from data shape.

Based on: energy-analysis-integration-plan.pdf
Reuses: weather.py (SMHI data), heating.py (COP models), import_vattenfall.py (hourly data)
"""

import numpy as np
from dataclasses import dataclass, field
from scipy import stats
from scipy.optimize import curve_fit


# === Swedish Benchmarks (Boverket BBR, Energimyndigheten) ===
BENCHMARKS = {
    "bbr_new_build_zone3": {"label": "BBR nybyggnad (zon 3)", "kwh_m2": 55},
    "passive_house": {"label": "Passivhus (FEBY)", "kwh_m2": 15},
    "average_detached": {"label": "Snitt svensk villa", "kwh_m2": 115},
    "well_insulated_1990s": {"label": "Välisolerat 1990-tal", "kwh_m2": 80},
    "poorly_insulated_pre1980": {"label": "Dåligt isolerat pre-1980", "kwh_m2": 175},
    "miljonprogrammet": {"label": "Miljonprogrammet 1960-70", "kwh_m2": 165},
}


# === Heating system definitions ===
HEATING_SYSTEMS = {
    "direct_electric": {
        "label": "Direktel (elpanna/elradiator)",
        "model": "linear",
        "cop": 1.0,
    },
    "ground_source": {
        "label": "Bergvärme",
        "model": "linear",
        "cop": 3.2,
        "cop_range": (2.8, 3.8),
    },
    "air_air": {
        "label": "Luft-luft värmepump",
        "model": "nonlinear",
        "cop_curve": {-20: 1.5, -15: 1.8, -10: 2.2, -5: 2.8, 0: 3.2, 5: 4.0, 10: 4.8, 15: 5.2},
        "backup_threshold": -15,
    },
    "air_water": {
        "label": "Luft-vatten värmepump",
        "model": "nonlinear",
        "cop_curve": {-20: 1.8, -15: 2.2, -10: 2.6, -5: 3.1, 0: 3.5, 5: 4.2, 10: 5.0, 15: 5.5},
        "backup_threshold": -20,
    },
}


@dataclass
class AnalysisResult:
    """Result of energy analysis."""
    # Building
    floor_area_m2: float = 0
    heating_system: str = ""
    detected_system: str = ""
    data_days: int = 0
    data_hours: int = 0

    # Model fit
    model_type: str = ""  # "linear" or "nonlinear"
    r_squared: float = 0
    baseload_kw: float = 0
    baseload_kwh_year: float = 0
    ua_value_w_per_k: float = 0
    specific_heat_loss: float = 0  # W/m²·K
    effective_cop: float = 0
    cop_source: str = ""  # "default", "calibrated", "user_specified"

    # Energy intensity
    total_kwh_m2_year: float = 0
    heating_kwh_m2_year: float = 0
    baseload_kwh_m2_year: float = 0

    # Calibration
    calibration_factor: float = 1.0
    rmse_before: float = 0
    rmse_after: float = 0

    # Energy signature data (for plotting)
    signature_x: list = field(default_factory=list)  # delta_T or T_outdoor
    signature_y: list = field(default_factory=list)  # daily kWh
    regression_x: list = field(default_factory=list)
    regression_y: list = field(default_factory=list)

    # Benchmark comparison
    benchmark_rating: str = ""
    benchmarks: dict = field(default_factory=dict)


def prepare_daily_data(hourly_consumption: list[dict],
                        hourly_temperatures: dict[str, list[tuple[int, float]]],
                        t_indoor: float = 21.0) -> list[dict]:
    """
    Aggregate hourly data to daily: total kWh, mean temperature, delta_T.

    Args:
        hourly_consumption: list of {"date": str, "hour": int, "kwh": float}
        hourly_temperatures: dict from weather.load_temperatures()
        t_indoor: indoor setpoint

    Returns list of {"date", "kwh", "t_mean", "delta_t"}
    """
    from collections import defaultdict

    # Sum consumption per day
    daily_kwh = defaultdict(float)
    for h in hourly_consumption:
        daily_kwh[h["date"]] += h["kwh"]

    # Mean temperature per day
    daily_temp = {}
    for date_str, hourly in hourly_temperatures.items():
        temps = [t for _, t in hourly]
        if temps:
            daily_temp[date_str] = sum(temps) / len(temps)

    # Merge
    result = []
    for date_str in sorted(daily_kwh.keys()):
        if date_str not in daily_temp:
            continue
        t_mean = daily_temp[date_str]
        delta_t = max(0, t_indoor - t_mean)
        result.append({
            "date": date_str,
            "kwh": daily_kwh[date_str],
            "t_mean": t_mean,
            "delta_t": delta_t,
        })

    return result


def fit_linear(daily_data: list[dict]) -> dict:
    """
    Fit linear model: daily_kwh = intercept + slope × delta_T

    Returns {"slope", "intercept", "r_squared", "baseload_kw", "residuals"}
    """
    x = np.array([d["delta_t"] for d in daily_data])
    y = np.array([d["kwh"] for d in daily_data])

    # Only fit on days with heating demand (delta_T > 0)
    mask = x > 0
    if mask.sum() < 30:
        # Not enough heating days — use all data
        mask = np.ones(len(x), dtype=bool)

    slope, intercept, r_value, p_value, std_err = stats.linregress(x[mask], y[mask])

    # Also compute summer baseline (T > 15°C) for better baseload estimate
    t_means = np.array([d["t_mean"] for d in daily_data])
    summer_mask = t_means > 15
    if summer_mask.sum() > 10:
        summer_baseline = np.mean(y[summer_mask])
    else:
        summer_baseline = intercept

    baseload_kw = summer_baseline / 24

    residuals = y - (intercept + slope * x)

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "baseload_kw": baseload_kw,
        "baseload_daily": summer_baseline,
        "residuals": residuals,
    }


def fit_nonlinear(daily_data: list[dict], cop_curve: dict) -> dict:
    """
    Fit nonlinear model for air-source heat pumps where COP varies with temperature.

    daily_kwh = baseload + UA/1000 × delta_T / COP(T_outdoor)
    """
    # Interpolate COP curve
    cop_temps = sorted(cop_curve.keys())
    cop_vals = [cop_curve[t] for t in cop_temps]

    def cop_interp(t):
        return float(np.interp(t, cop_temps, cop_vals))

    t_outdoor = np.array([d["t_mean"] for d in daily_data])
    delta_t = np.array([d["delta_t"] for d in daily_data])
    y = np.array([d["kwh"] for d in daily_data])

    # Model: y = baseload_daily + (ua_factor × delta_T / COP(T))
    def model(x, baseload_daily, ua_factor):
        t_out, dt = x
        cop = np.array([max(1.0, cop_interp(t)) for t in t_out])
        return baseload_daily + ua_factor * dt / cop

    try:
        popt, pcov = curve_fit(model, (t_outdoor, delta_t), y,
                                p0=[40.0, 2.0], maxfev=10000)
        baseload_daily, ua_factor = popt
        y_pred = model((t_outdoor, delta_t), *popt)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    except Exception:
        return {"slope": 0, "intercept": 0, "r_squared": 0, "baseload_kw": 0,
                "ua_factor": 0, "residuals": np.zeros(len(y))}

    return {
        "baseload_daily": baseload_daily,
        "baseload_kw": baseload_daily / 24,
        "ua_factor": ua_factor,
        "r_squared": r_squared,
        "residuals": y - y_pred,
    }


def detect_heating_system(daily_data: list[dict]) -> str:
    """
    Auto-detect heating system type from energy signature shape.

    Returns one of: "direct_electric", "ground_source", "air_air", "air_water"
    """
    # Fit linear model
    linear = fit_linear(daily_data)

    # Check for nonlinearity: fit quadratic and compare R²
    x = np.array([d["delta_t"] for d in daily_data])
    y = np.array([d["kwh"] for d in daily_data])
    t_outdoor = np.array([d["t_mean"] for d in daily_data])

    mask = x > 0
    if mask.sum() < 30:
        return "ground_source"  # not enough data, default

    # Quadratic fit on consumption vs outdoor temperature (not delta_T)
    cold_mask = t_outdoor < 10
    if cold_mask.sum() > 20:
        coeffs = np.polyfit(t_outdoor[cold_mask], y[cold_mask], 2)
        y_quad = np.polyval(coeffs, t_outdoor[cold_mask])
        ss_res_quad = np.sum((y[cold_mask] - y_quad) ** 2)
        ss_tot = np.sum((y[cold_mask] - np.mean(y[cold_mask])) ** 2)
        r2_quad = 1 - ss_res_quad / ss_tot if ss_tot > 0 else 0
    else:
        r2_quad = 0

    r2_linear = linear["r_squared"]

    # Check for kink (slope change at low temperatures)
    very_cold = t_outdoor < -10
    mild_cold = (t_outdoor >= -10) & (t_outdoor < 5)
    if very_cold.sum() > 10 and mild_cold.sum() > 20:
        slope_cold, _, _, _, _ = stats.linregress(x[very_cold], y[very_cold])
        slope_mild, _, _, _, _ = stats.linregress(x[mild_cold], y[mild_cold])
        slope_ratio = slope_cold / slope_mild if slope_mild > 0 else 1
    else:
        slope_ratio = 1.0

    # Decision logic
    if r2_quad - r2_linear > 0.03:
        # Significant nonlinearity → air source
        if slope_ratio > 1.5:
            return "air_air"  # kink suggests backup heater
        return "air_water"

    # Linear system — distinguish by slope
    # slope = UA / (COP × 1000) × 24
    # High slope (>3 kWh/day/°C for 150m²) suggests COP≈1 (direct electric)
    # Low slope (<1.5 kWh/day/°C for 150m²) suggests COP≈3 (ground source)
    slope = linear["slope"]
    if slope > 2.5:
        return "direct_electric"
    else:
        return "ground_source"


def analyze(hourly_consumption: list[dict],
            hourly_temperatures: dict[str, list[tuple[int, float]]],
            floor_area_m2: float = 150,
            heating_system: str = "auto",
            t_indoor: float = 21.0,
            monthly_bills: list[dict] = None) -> AnalysisResult:
    """
    Run the full energy analysis.

    Args:
        hourly_consumption: from Vattenfall import or Tibber
        hourly_temperatures: from weather.load_temperatures()
        floor_area_m2: building floor area
        heating_system: "auto", "direct_electric", "ground_source", "air_air", "air_water"
        t_indoor: indoor temperature setpoint
        monthly_bills: optional [{"month": "2023-01", "kwh": 3200}, ...]

    Returns AnalysisResult with all metrics.
    """
    result = AnalysisResult(floor_area_m2=floor_area_m2)
    result.data_hours = len(hourly_consumption)

    # Prepare daily aggregates
    daily = prepare_daily_data(hourly_consumption, hourly_temperatures, t_indoor)
    result.data_days = len(daily)

    if len(daily) < 60:
        return result  # not enough data

    # Auto-detect heating system if needed
    if heating_system == "auto":
        detected = detect_heating_system(daily)
        result.detected_system = detected
        result.heating_system = detected
    else:
        result.heating_system = heating_system
        result.detected_system = heating_system

    sys_info = HEATING_SYSTEMS.get(result.heating_system, HEATING_SYSTEMS["ground_source"])

    # Fit model
    if sys_info["model"] == "linear":
        fit = fit_linear(daily)
        result.model_type = "linear"
        result.r_squared = fit["r_squared"]
        result.baseload_kw = fit["baseload_kw"]
        result.baseload_kwh_year = result.baseload_kw * 8760

        # COP and UA
        cop = sys_info.get("cop", 3.2)
        result.effective_cop = cop
        result.cop_source = "default"

        # UA = slope × COP × 1000 / 24
        slope = fit["slope"]
        result.ua_value_w_per_k = round(slope * cop * 1000 / 24, 1)

    else:
        # Nonlinear (air source)
        cop_curve = sys_info.get("cop_curve", {0: 3.0})
        fit = fit_nonlinear(daily, cop_curve)
        result.model_type = "nonlinear"
        result.r_squared = fit.get("r_squared", 0)
        result.baseload_kw = fit.get("baseload_kw", 0)
        result.baseload_kwh_year = result.baseload_kw * 8760

        # UA from ua_factor: ua_factor = UA / 1000 × 24
        result.ua_value_w_per_k = round(fit.get("ua_factor", 0) * 1000 / 24, 1)
        result.effective_cop = 0  # varies with temperature
        result.cop_source = "curve"

    # Specific heat loss
    if floor_area_m2 > 0:
        result.specific_heat_loss = round(result.ua_value_w_per_k / floor_area_m2, 2)

    # Energy intensity
    total_kwh = sum(d["kwh"] for d in daily)
    years = len(daily) / 365.25
    annual_kwh = total_kwh / years if years > 0 else 0

    if floor_area_m2 > 0:
        result.total_kwh_m2_year = round(annual_kwh / floor_area_m2, 1)
        result.baseload_kwh_m2_year = round(result.baseload_kwh_year / floor_area_m2, 1)
        result.heating_kwh_m2_year = round(result.total_kwh_m2_year - result.baseload_kwh_m2_year, 1)

    # Calibration against bills
    if monthly_bills:
        result = _calibrate(result, daily, monthly_bills, sys_info)

    # Energy signature data for plotting
    result.signature_x = [d["delta_t"] for d in daily]
    result.signature_y = [d["kwh"] for d in daily]

    # Regression line
    x_range = [0, max(d["delta_t"] for d in daily) if daily else 40]
    if result.model_type == "linear":
        fit_lin = fit_linear(daily)
        result.regression_x = x_range
        result.regression_y = [fit_lin["intercept"] + fit_lin["slope"] * x for x in x_range]

    # Benchmark comparison
    result.benchmarks = {k: v["kwh_m2"] for k, v in BENCHMARKS.items()}
    total = result.total_kwh_m2_year
    if total > 0:
        if total <= 55:
            result.benchmark_rating = "Utmärkt — uppfyller BBR nybyggnadskrav"
        elif total <= 80:
            result.benchmark_rating = "Bra — bättre än de flesta svenska villor"
        elif total <= 115:
            result.benchmark_rating = "Genomsnittligt — typisk svensk villa"
        elif total <= 160:
            result.benchmark_rating = "Under genomsnittet — potential för förbättring"
        else:
            result.benchmark_rating = "Hög förbrukning — stor potential för energieffektivisering"

    return result


def _calibrate(result: AnalysisResult, daily: list[dict],
               monthly_bills: list[dict], sys_info: dict) -> AnalysisResult:
    """Calibrate model against monthly electricity bills."""
    from collections import defaultdict

    # Aggregate daily predictions to monthly
    monthly_predicted = defaultdict(float)
    for d in daily:
        ym = d["date"][:7]
        monthly_predicted[ym] += d["kwh"]  # This is actual data, not model prediction

    # Compare with bills
    bill_map = {b["month"]: b["kwh"] for b in monthly_bills}

    pairs = []
    for ym in sorted(set(monthly_predicted.keys()) & set(bill_map.keys())):
        pairs.append((monthly_predicted[ym], bill_map[ym]))

    if not pairs:
        return result

    predicted = np.array([p for p, _ in pairs])
    actual = np.array([a for _, a in pairs])

    # RMSE before calibration
    result.rmse_before = float(np.sqrt(np.mean((predicted - actual) ** 2)))

    # Calibration factor
    result.calibration_factor = float(np.sum(actual) / np.sum(predicted)) if np.sum(predicted) > 0 else 1.0

    # RMSE after
    calibrated = predicted * result.calibration_factor
    result.rmse_after = float(np.sqrt(np.mean((calibrated - actual) ** 2)))

    # For ground source: adjust COP based on calibration
    if sys_info.get("model") == "linear" and result.heating_system == "ground_source":
        # If calibration_factor > 1: actual uses more than predicted → COP is lower than assumed
        result.effective_cop = sys_info.get("cop", 3.2) / result.calibration_factor
        result.cop_source = "calibrated"
        # Recompute UA with calibrated COP
        fit = fit_linear(daily)
        result.ua_value_w_per_k = round(fit["slope"] * result.effective_cop * 1000 / 24, 1)
        if result.floor_area_m2 > 0:
            result.specific_heat_loss = round(result.ua_value_w_per_k / result.floor_area_m2, 2)

    return result
