"""
Heating model — splits electricity consumption into heating and base load.

Uses outdoor temperature to model heat pump electricity consumption,
enabling hour-by-hour self-consumption vs export decisions.

Ground-source heat pump (bergvärme) with stable ground temp ~8°C.
"""

import csv
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HeatingConfig:
    """Configuration for heating model."""
    h_loss: float = 0.160         # kW per °C — calibrated from 2024+2025 Tibber data
    t_indoor: float = 21.0        # °C indoor setpoint
    cop_base: float = 3.4         # COP at 0°C outdoor
    cop_slope: float = 0.056      # COP increase per °C outdoor
    cop_min: float = 1.0          # minimum COP (elpatron territory)
    hp_max_heat_kw: float = 6.0   # max heat output from heat pump (kW thermal)
    elpatron_kw: float = 3.0      # supplementary electric heater capacity
    dhw_kwh_per_day: float = 8.0  # domestic hot water electricity (kWh/day)
    dhw_cop: float = 2.3          # COP for DHW heating (higher supply temp)


def cop_ground_source(t_outdoor: float, config: HeatingConfig) -> float:
    """COP for ground-source heat pump as function of outdoor temperature."""
    cop = config.cop_base + config.cop_slope * t_outdoor
    return max(config.cop_min, cop)


def heating_demand_kw(t_outdoor: float, config: HeatingConfig) -> float:
    """Thermal heating demand in kW (heat needed by house)."""
    delta_t = max(0, config.t_indoor - t_outdoor)
    return config.h_loss * delta_t


def heating_electricity_kw(t_outdoor: float, config: HeatingConfig) -> float:
    """Electricity consumed by heat pump + elpatron for space heating.

    Returns total electrical power (kW) for space heating at given outdoor temp.
    """
    demand_kw = heating_demand_kw(t_outdoor, config)
    if demand_kw <= 0:
        return 0.0

    cop = cop_ground_source(t_outdoor, config)

    # Heat pump covers up to its max thermal output
    hp_heat = min(demand_kw, config.hp_max_heat_kw)
    hp_elec = hp_heat / cop

    # Elpatron covers the rest (COP = 1.0)
    shortfall = demand_kw - hp_heat
    elpatron_elec = min(shortfall, config.elpatron_kw) if shortfall > 0 else 0

    return hp_elec + elpatron_elec


def base_load_from_total(total_daily_kwh: float, heating_daily_kwh: float,
                          dhw_daily_kwh: float) -> float:
    """Derive base electrical load from total consumption minus heating and DHW."""
    return max(0, total_daily_kwh - heating_daily_kwh - dhw_daily_kwh)


def load_temperatures(cache_path: str = None, station_id: str = "97400"
                      ) -> dict[str, list[tuple[int, float]]]:
    """Load temperature data from cache.

    Args:
        cache_path: explicit path to CSV (legacy support)
        station_id: SMHI station ID (default: Arlanda 97400)

    Returns dict: date_str -> [(hour, temp_c), ...]
    """
    if cache_path is not None:
        path = cache_path
    else:
        # Try new weather module first
        try:
            from weather import load_temperatures as _wload
            return _wload(station_id)
        except ImportError:
            path = ".weather_cache/arlanda_temp.csv"

    if not os.path.exists(path):
        return {}

    temps: dict[str, list[tuple[int, float]]] = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["date"]
            hour = int(row["hour"])
            temp = float(row["temp_c"])
            temps.setdefault(date, []).append((hour, temp))
    return temps


def build_hourly_heating_profile(temps: dict[str, list[tuple[int, float]]],
                                  config: HeatingConfig
                                  ) -> dict[str, dict[int, float]]:
    """Build hourly heating electricity consumption from temperature data.

    Returns dict: date_str -> {hour: heating_elec_kw}
    """
    profile: dict[str, dict[int, float]] = {}
    for date, hourly in temps.items():
        day_profile: dict[int, float] = {}
        for hour, temp in hourly:
            day_profile[hour] = heating_electricity_kw(temp, config)
        profile[date] = day_profile
    return profile


def fit_heating_model(consumption_daily: list[dict],
                       temps: dict[str, list[tuple[int, float]]],
                       config: Optional[HeatingConfig] = None
                       ) -> HeatingConfig:
    """Fit heating model parameters to actual consumption + temperature data.

    consumption_daily: list of {"date": "YYYY-MM-DD", "consumption_kwh": float}
    temps: from load_temperatures()

    Adjusts h_loss to match actual consumption pattern.
    Returns a calibrated HeatingConfig.
    """
    if config is None:
        config = HeatingConfig()

    # Pair consumption with daily average temperature
    pairs = []
    for row in consumption_daily:
        date = row["date"]
        kwh = row["consumption_kwh"]
        if date in temps:
            day_temps = [t for _, t in temps[date]]
            avg_temp = sum(day_temps) / len(day_temps) if day_temps else None
            if avg_temp is not None:
                pairs.append((avg_temp, kwh))

    if len(pairs) < 30:
        return config  # not enough data to fit

    # Summer baseline (T > 15°C): minimal heating, gives us base + DHW
    summer = [kwh for t, kwh in pairs if t > 15]
    if summer:
        summer_baseline = sum(summer) / len(summer)
    else:
        summer_baseline = min(kwh for _, kwh in pairs)

    # Base load (non-heating) = summer baseline - DHW
    base_daily = summer_baseline - config.dhw_kwh_per_day

    # Winter data (T < 5°C): fit h_loss
    winter = [(t, kwh) for t, kwh in pairs if t < 5]
    if len(winter) < 10:
        return config

    # For each winter day: heating_elec = total - base - dhw
    # heating_elec = h_loss * (21 - T) / COP(T)
    # Solve for h_loss using least squares
    sum_xy = 0.0
    sum_xx = 0.0
    for t, kwh in winter:
        heating_elec = max(0, kwh - base_daily - config.dhw_kwh_per_day)
        cop = cop_ground_source(t, config)
        # Over 24 hours: heating_elec (kWh/day) = 24 * h_loss * (21 - T) / COP
        # So: h_loss = heating_elec * COP / (24 * (21 - T))
        delta_t = config.t_indoor - t
        if delta_t > 0:
            x = 24 * delta_t / cop  # expected heating_elec per unit h_loss
            sum_xy += x * heating_elec
            sum_xx += x * x

    if sum_xx > 0:
        fitted_h = sum_xy / sum_xx
        config = HeatingConfig(
            h_loss=round(fitted_h, 4),
            t_indoor=config.t_indoor,
            cop_base=config.cop_base,
            cop_slope=config.cop_slope,
            cop_min=config.cop_min,
            hp_max_heat_kw=config.hp_max_heat_kw,
            elpatron_kw=config.elpatron_kw,
            dhw_kwh_per_day=config.dhw_kwh_per_day,
            dhw_cop=config.dhw_cop,
        )

    return config


def split_consumption(total_daily_kwh: float, t_outdoor_hourly: list[float],
                       config: HeatingConfig
                       ) -> dict:
    """Split a day's consumption into heating, DHW, and base components.

    Returns dict with kWh breakdown for the day.
    """
    # Heating electricity per hour
    heating_hours = [heating_electricity_kw(t, config) for t in t_outdoor_hourly]
    heating_kwh = sum(heating_hours)  # kWh (1 hour per sample)

    dhw_kwh = config.dhw_kwh_per_day
    base_kwh = max(0, total_daily_kwh - heating_kwh - dhw_kwh)

    return {
        "heating_kwh": heating_kwh,
        "dhw_kwh": dhw_kwh,
        "base_kwh": base_kwh,
        "total_kwh": total_daily_kwh,
        "heating_fraction": heating_kwh / total_daily_kwh if total_daily_kwh > 0 else 0,
    }


def hourly_consumption_profile(t_outdoor_hourly: list[float],
                                base_load_kw: float,
                                config: HeatingConfig
                                ) -> list[float]:
    """Generate hourly electricity consumption profile for a day.

    Combines: heating (temperature-dependent) + DHW (spread over day) + base load.
    Returns list of 24 kW values.
    """
    profile = []
    dhw_per_hour = config.dhw_kwh_per_day / 24  # spread evenly

    for i, t in enumerate(t_outdoor_hourly[:24]):
        heat_kw = heating_electricity_kw(t, config)
        total_kw = base_load_kw + heat_kw + dhw_per_hour
        profile.append(round(total_kw, 3))

    return profile
