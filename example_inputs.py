"""
Example figures the app starts with (pure, no Streamlit).

Technical defaults (efficiency, wear, tariffs, ...) are neutral assumptions. The
personal figures below are only an example so the app works on a first visit:
the visitor's own prices, panel size and house replace them. app.py takes the
widget defaults from here, and untouched_examples() compares the inputs of a
simulation with the same values, so the "example calculation" warning can't
drift from the widgets.
"""

# NKON ESS Pro list prices, EUR excl. VAT (~Q1 2025): (name, capacity kWh, max kW, EUR)
NKON_BATTERIES = [
    ("5 kWh", 5.12, 3.8, 600),
    ("10 kWh", 10.24, 7.5, 1177),
    ("16 kWh", 16.10, 11.0, 1512),
    ("32 kWh", 32.15, 15.0, 2857),
    ("32+16 kWh", 48.25, 15.0, 2857 + 1512),
    ("2x32 kWh", 64.30, 15.0, 2857 * 2),
    ("2x32+16 kWh", 80.40, 15.0, 2857 * 2 + 1512),
    ("3x32 kWh", 96.45, 15.0, 2857 * 3),
]
BATTERY_VAT = 1.25  # NKON prices are excl. Swedish VAT; a private buyer pays 25 % on top

EXAMPLE = {
    "eur_sek": 11.5,
    "sek_per_kwh": 1000,       # SEK/kWh pricing mode
    "bat_install": 10000,
    "solar_kwp": 15.0,
    "sol_price": 48000,        # DIY: material only, own mounting
    "sol_install": 0,
    "energy_class": "C",
    "house_area": 150,
    "heating_type": "heating_ground",
}

# Quick-add templates for loads (names are set from translations when added)
EV_LOAD = {"power": 11.0, "start": 18, "end": 7, "daily_kwh": 30.0, "smart": True}
POOL_HEAT_PUMP_LOAD = {"power": 3.0, "daily": 20.0, "sm": 5, "em": 9}  # May-Sep, waits for surplus
HOT_WATER_LOAD = {"name": "Varmvatten", "power": 3.0, "daily": 10.0, "sm": 1, "em": 12}


def default_battery_rows(eur_sek) -> list[dict]:
    """The default battery price table (SEK incl. VAT) for an EUR/SEK rate."""
    return [{"Namn": name, "Kapacitet_kWh": cap, "Max_kW": max_kw,
             "Pris_SEK": round(eur * eur_sek * BATTERY_VAT)}
            for name, cap, max_kw, eur in NKON_BATTERIES]


def _same_rows(rows, default_rows) -> bool:
    if len(rows) != len(default_rows):
        return False
    for (name, cap, max_kw, price), d in zip(rows, default_rows):
        if (str(name) != d["Namn"] or round(float(cap), 2) != round(d["Kapacitet_kWh"], 2)
                or round(float(max_kw), 2) != round(d["Max_kW"], 2)
                or round(float(price)) != d["Pris_SEK"]):
            return False
    return True


def untouched_examples(si: dict) -> list[str]:
    """Which personal figures of a simulation are still the untouched examples.

    si: the inputs snapshotted at simulation time. Keys used: pricing_mode
    ("table"/"sek_kwh"), battery_rows [(name, kWh, max kW, price)], eur_sek,
    sek_per_kwh, bat_install, use_solar, solar_kwp, sol_price, sol_install,
    use_heating_model, own_consumption (Tibber, uploaded data or Tibber-Insights
    calibration), energy_class, house_area, heating_type.

    Returns item ids in display order: "battery_prices", "battery_install",
    "solar_kwp", "solar_price", "house". Grid operator, fuse and phases are not
    judged by value (a real customer can have exactly the default).
    """
    items = []
    if si.get("pricing_mode") == "sek_kwh":
        if si.get("sek_per_kwh") == EXAMPLE["sek_per_kwh"]:
            items.append("battery_prices")
    elif si.get("eur_sek") is not None and _same_rows(si.get("battery_rows", []),
                                                      default_battery_rows(si["eur_sek"])):
        items.append("battery_prices")
    if si.get("bat_install") == EXAMPLE["bat_install"]:
        items.append("battery_install")
    if si.get("use_solar") and si.get("solar_kwp", 0) > 0:
        if si.get("solar_kwp") == EXAMPLE["solar_kwp"]:
            items.append("solar_kwp")
        if (si.get("sol_price") == EXAMPLE["sol_price"]
                and si.get("sol_install") == EXAMPLE["sol_install"]):
            items.append("solar_price")
    if (si.get("use_heating_model") and not si.get("own_consumption")
            and si.get("energy_class") == EXAMPLE["energy_class"]
            and si.get("house_area") == EXAMPLE["house_area"]
            and si.get("heating_type") == EXAMPLE["heating_type"]):
        items.append("house")
    return items
