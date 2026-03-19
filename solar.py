"""
Solar production model for Swedish installations.

Estimates hourly PV production based on:
- System size (kWp)
- Location (Stockholm default, lat 59.3°N)
- Panel orientation (south-facing default)
- Monthly irradiance data and day length

Uses typical monthly kWh/kWp values for Stockholm south-facing ~35° tilt,
distributed across daylight hours using a cosine bell curve.
"""

import math
from dataclasses import dataclass


# Typical monthly production per kWp (kWh) for Stockholm, south-facing ~35° tilt
# Source: PVGIS / Energimyndigheten typical values
MONTHLY_KWH_PER_KWP = {
    1: 15,    # Jan
    2: 35,    # Feb
    3: 75,    # Mar
    4: 110,   # Apr
    5: 140,   # May
    6: 145,   # Jun
    7: 140,   # Jul
    8: 115,   # Aug
    9: 75,    # Sep
    10: 40,   # Oct
    11: 15,   # Nov
    12: 8,    # Dec
}

# Approximate sunrise/sunset hours for Stockholm (solar time, mid-month)
DAYLIGHT_HOURS = {
    1:  (8.5, 15.5),   # Jan: ~7h daylight
    2:  (7.5, 16.5),   # Feb: ~9h
    3:  (6.5, 18.0),   # Mar: ~11.5h
    4:  (5.5, 19.5),   # Apr: ~14h
    5:  (4.0, 21.0),   # May: ~17h
    6:  (3.5, 21.5),   # Jun: ~18h
    7:  (4.0, 21.0),   # Jul: ~17h
    8:  (5.0, 20.0),   # Aug: ~15h
    9:  (6.5, 18.5),   # Sep: ~12h
    10: (7.5, 17.0),   # Oct: ~9.5h
    11: (8.0, 15.5),   # Nov: ~7.5h
    12: (9.0, 15.0),   # Dec: ~6h
}


@dataclass
class SolarConfig:
    """Solar panel configuration."""
    capacity_kwp: float = 15.0         # system size in kWp
    orientation: str = "south"         # panel orientation
    tilt: float = 35.0                 # tilt angle (degrees)
    performance_ratio: float = 0.85    # system losses (inverter, cables, dirt, etc.)
    location: str = "Stockholm"
    # Investment
    purchase_price: float = 0.0        # total cost for panels + inverter (SEK)
    installation_cost: float = 0.0     # installation cost (SEK)
    lifetime_years: int = 25           # expected panel lifetime
    degradation_per_year: float = 0.005  # annual production loss (0.5%/year typical)


def hourly_production_factors(month: int) -> dict[int, float]:
    """
    Get production factor for each hour of the day (0-23).

    Returns a dict mapping hour -> fraction of daily production.
    Uses a cosine curve between sunrise and sunset, centered at solar noon.
    """
    sunrise, sunset = DAYLIGHT_HOURS[month]
    solar_noon = (sunrise + sunset) / 2
    half_day = (sunset - sunrise) / 2

    factors = {}
    total = 0
    for h in range(24):
        # Check quarter-hours for smoother result
        hour_sum = 0
        for q in [0.0, 0.25, 0.5, 0.75]:
            t = h + q
            if sunrise <= t <= sunset:
                # cos² curve: more realistic peak concentration than cos
                # Real panels peak around noon, low output at dawn/dusk
                angle = (t - solar_noon) / half_day * (math.pi / 2)
                cos_val = max(0, math.cos(angle))
                hour_sum += cos_val ** 3  # cos³ for realistic peak concentration
        factors[h] = hour_sum / 4  # average of 4 quarter-hours
        total += factors[h]

    # Normalize so factors sum to 1.0
    if total > 0:
        for h in factors:
            factors[h] /= total

    return factors


def get_solar_production(month: int, hour: int, config: SolarConfig) -> float:
    """
    Estimated solar production in kW for a given month and hour.

    Returns average production in kW for that hour of the month.
    """
    monthly_kwh = MONTHLY_KWH_PER_KWP[month] * config.capacity_kwp * config.performance_ratio
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month]
    daily_kwh = monthly_kwh / days_in_month

    factors = hourly_production_factors(month)
    # Factor gives fraction of daily production for this hour
    # Since each slot is 1 hour, kWh = kW for that hour
    return daily_kwh * factors[hour]


def get_solar_for_slot(date_str: str, hour_str: str, config: SolarConfig) -> float:
    """
    Get solar production in kW for a specific date and hour slot.
    """
    month = int(date_str.split("-")[1])
    hour = int(hour_str.split(":")[0])
    return get_solar_production(month, hour, config)


def estimate_yearly_production(config: SolarConfig) -> float:
    """Estimated total yearly production in kWh."""
    total = sum(MONTHLY_KWH_PER_KWP.values())
    return total * config.capacity_kwp * config.performance_ratio


def estimate_lifetime_production(config: SolarConfig) -> float:
    """Total production over lifetime accounting for degradation."""
    yearly_base = estimate_yearly_production(config)
    total = 0
    for year in range(config.lifetime_years):
        total += yearly_base * (1 - config.degradation_per_year) ** year
    return total


def print_solar_info(config: SolarConfig):
    """Print solar system summary."""
    yearly = estimate_yearly_production(config)
    print(f"  Solceller:        {config.capacity_kwp} kWp, {config.orientation}, {config.tilt}° lutning")
    print(f"  Plats:            {config.location}")
    print(f"  Systemförluster:  {(1-config.performance_ratio)*100:.0f}%")
    print(f"  Degradering:      {config.degradation_per_year*100:.1f}%/år")
    print(f"  Beräknad årsproduktion: {yearly:.0f} kWh/år")
    print(f"  Månadsproduktion (kWh):")
    months_sv = ["", "Jan", "Feb", "Mar", "Apr", "Maj", "Jun",
                 "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]
    for m in range(1, 13):
        kwh = MONTHLY_KWH_PER_KWP[m] * config.capacity_kwp * config.performance_ratio
        bar = "█" * int(kwh / 40)
        print(f"    {months_sv[m]}: {kwh:>6.0f} kWh {bar}")
