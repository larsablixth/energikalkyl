"""
Compare calibration results: custom (heating.py) vs BEMServer-style (energy_analysis.py).

Runs both pipelines on the same data and prints side-by-side results.
Uses real SMHI weather data + synthetic consumption based on known house parameters.
"""

import sys
import os

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(__file__))

from heating import HeatingConfig, fit_heating_model, cop_ground_source
from bemserver_store import store_and_cleanse
from energy_analysis import analyze as ea_analyze
from weather import load_temperatures


def generate_consumption(temps_data, config):
    """Generate realistic hourly consumption from known HeatingConfig + weather."""
    import random
    random.seed(42)

    hourly_consumption = []
    daily_consumption = []

    for date_str in sorted(temps_data.keys()):
        hourly_temps = temps_data[date_str]
        daily_kwh = 0
        for hour, t_outdoor in hourly_temps:
            # Heating electricity
            delta_t = max(0, config.t_indoor - t_outdoor)
            cop = cop_ground_source(t_outdoor, config)
            heat_demand = config.h_loss * delta_t
            hp_heat = min(heat_demand, config.hp_max_heat_kw)
            hp_elec = hp_heat / cop if cop > 0 else 0
            shortfall = heat_demand - hp_heat
            elpatron = min(shortfall, config.elpatron_kw) if shortfall > 0 else 0

            # DHW spread over day
            dhw = config.dhw_kwh_per_day / 24

            # Base load (non-heating)
            base = 0.68

            # Add some noise (±10%)
            total = (hp_elec + elpatron + dhw + base) * (1 + random.gauss(0, 0.05))
            total = max(0.1, total)

            hourly_consumption.append({
                "date": date_str, "hour": hour, "kwh": round(total, 3)
            })
            daily_kwh += total

        daily_consumption.append({
            "date": date_str, "consumption_kwh": round(daily_kwh, 2)
        })

    return hourly_consumption, daily_consumption


def build_seasonal_profile(hourly_consumption):
    """Convert hourly data to seasonal profile (month → hour → avg kWh)."""
    from collections import defaultdict
    month_hour_vals = defaultdict(lambda: defaultdict(list))
    for r in hourly_consumption:
        month = int(r["date"].split("-")[1])
        month_hour_vals[month][r["hour"]].append(r["kwh"])
    return {
        m: {h: sum(vals)/len(vals) for h, vals in hours.items()}
        for m, hours in month_hour_vals.items()
    }


def main():
    # Load real weather data (Arlanda)
    print("Loading SMHI weather data (Arlanda)...")
    temps_data = load_temperatures(station_id="97400")
    if not temps_data:
        print("ERROR: No weather data. Run the app first to cache SMHI data.")
        sys.exit(1)

    # Filter to 2 full years for fair comparison
    dates = sorted(temps_data.keys())
    print(f"Weather data: {dates[0]} to {dates[-1]} ({len(dates)} days)")

    # Use known house parameters (from CLAUDE.md verified values)
    true_config = HeatingConfig(
        h_loss=0.160,       # kW/°C — calibrated ground truth
        cop_base=3.4,
        cop_slope=0.056,
        hp_max_heat_kw=6.0,
        elpatron_kw=3.0,
        dhw_kwh_per_day=6.0,
    )
    print(f"\nGround truth: h_loss={true_config.h_loss} kW/°C")
    print(f"  COP model: {true_config.cop_base} + {true_config.cop_slope}×T")
    print(f"  HP max: {true_config.hp_max_heat_kw} kW, elpatron: {true_config.elpatron_kw} kW")

    # Generate synthetic consumption from known parameters
    print("\nGenerating synthetic consumption from ground truth...")
    hourly_consumption, daily_consumption = generate_consumption(temps_data, true_config)
    total_kwh = sum(r["kwh"] for r in hourly_consumption)
    years = len(dates) / 365.25
    print(f"  Total: {total_kwh:.0f} kWh over {years:.1f} years ({total_kwh/years:.0f} kWh/yr)")

    # === Method 1: Custom (heating.py fit_heating_model) ===
    print("\n" + "="*60)
    print("METHOD 1: Custom (heating.py fit_heating_model)")
    print("="*60)

    starting_config = HeatingConfig(h_loss=0.200)  # intentionally wrong starting point
    fitted = fit_heating_model(daily_consumption, temps_data, starting_config)
    print(f"  h_loss:     {fitted.h_loss:.4f} kW/°C  (true: {true_config.h_loss})")
    print(f"  Error:      {abs(fitted.h_loss - true_config.h_loss):.4f} kW/°C "
          f"({abs(fitted.h_loss - true_config.h_loss)/true_config.h_loss*100:.1f}%)")

    # === Method 2: BEMServer-style (energy_analysis.py) ===
    print("\n" + "="*60)
    print("METHOD 2: BEMServer-style (bemserver_store + energy_analysis)")
    print("="*60)

    # Clean previous cache
    import shutil
    if os.path.exists(".bemserver_cache"):
        shutil.rmtree(".bemserver_cache")

    cleansed = store_and_cleanse(hourly_consumption, temps_data, source="synthetic")
    print(f"  Cleansed: {len(cleansed['hourly_consumption'])} consumption records")
    print(f"  Cleansed: {len(cleansed['hourly_temperatures'])} temperature days")

    # Check completeness
    cons_comp = cleansed["completeness"].get("consumption", {})
    incomplete = {m: v for m, v in cons_comp.items() if v < 1.0}
    if incomplete:
        print(f"  Incomplete months: {incomplete}")
    else:
        print(f"  Data completeness: 100% all months")

    result = ea_analyze(
        cleansed["hourly_consumption"],
        cleansed["hourly_temperatures"],
        floor_area_m2=270,
        heating_system="auto"
    )

    ea_h_loss = result.ua_value_w_per_k / 1000
    print(f"  Detected system: {result.detected_system}")
    print(f"  Model type:      {result.model_type}")
    print(f"  R²:              {result.r_squared:.4f}")
    print(f"  UA value:        {result.ua_value_w_per_k:.1f} W/K")
    print(f"  h_loss:          {ea_h_loss:.4f} kW/°C  (true: {true_config.h_loss})")
    print(f"  Error:           {abs(ea_h_loss - true_config.h_loss):.4f} kW/°C "
          f"({abs(ea_h_loss - true_config.h_loss)/true_config.h_loss*100:.1f}%)")
    print(f"  Baseload:        {result.baseload_kw:.2f} kW")
    print(f"  Effective COP:   {result.effective_cop:.2f}")
    print(f"  kWh/m²/yr:       {result.total_kwh_m2_year}")
    print(f"  Rating:          {result.benchmark_rating}")

    # === Side-by-side comparison ===
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    print(f"{'':30s} {'Custom':>12s} {'BEMServer':>12s} {'True':>12s}")
    print(f"{'-'*30} {'-'*12} {'-'*12} {'-'*12}")
    print(f"{'h_loss (kW/°C)':30s} {fitted.h_loss:12.4f} {ea_h_loss:12.4f} {true_config.h_loss:12.4f}")
    print(f"{'Error (%)':30s} {abs(fitted.h_loss-true_config.h_loss)/true_config.h_loss*100:11.1f}% "
          f"{abs(ea_h_loss-true_config.h_loss)/true_config.h_loss*100:11.1f}%")

    winner = "Custom" if abs(fitted.h_loss - true_config.h_loss) < abs(ea_h_loss - true_config.h_loss) else "BEMServer"
    print(f"\nCloser to ground truth: {winner}")

    # Clean up
    if os.path.exists(".bemserver_cache"):
        shutil.rmtree(".bemserver_cache")


if __name__ == "__main__":
    main()
