# CLAUDE.md

## Project: Energikalkyl — El, Sol & Batteri

Swedish electricity investment analysis tool. Answers: "Should I buy a home battery and/or solar panels, and if so, what size?" Simulates profitability based on historical spot prices, real weather data, actual consumption patterns, grid operator tariffs (including effekttariff), and financing via mortgage.

## How to run
```bash
streamlit run app.py                    # Web GUI on port 8501
docker compose up                       # Docker (no Python needed)
python elpriser.py batteri --help       # CLI help
```

## Architecture overview

The app follows a 6-step flow:
1. **Load data** — spot prices from elprisetjustnu.se API or CSV, optional consumption from Tibber/Vattenfall
2. **Configure setup** — grid operator, fuse, solar, loads, heating model (auto-calibrated from weather + consumption)
3. **Investment** — editable battery price table (NKON defaults), installation, solar costs, financing (bolån/kontant)
4. **Results** — simulates ALL battery sizes × ALL tariffs, recommends optimal. Scenario comparison (normal vs high-price years)
5. **Detail view** — monthly breakdown for selected battery, "with vs without" cost comparison
6. **Future outlook** — volatility sensitivity analysis

## Key files

### Core simulation
- `batteri.py` — Battery simulation engine. `BatteryConfig` dataclass, `simulate()` function. Multi-cycle scheduling, solar-aware, fuse headroom-limited. Supports `daily_load_override` for temperature-dependent load profiles.
- `solar.py` — Solar production model (cos³ curve, configurable kWp, Stockholm south-facing 35° tilt, monthly averages)

### Tariffs & grid operators
- `tariff.py` — Grid tariff models: `Tidstariff`, `FastTariff`, `EffektTariff`. `GRID_OPERATORS` dict with presets for:
  - Vattenfall Eldistribution (tidstariff + enkeltariff, no effekttariff for private yet)
  - Ellevio (effekttariff: 81.25 kr/kW/mån, top-3 peaks, 50% night discount)
  - E.ON Energidistribution (tid + enkel)
  - Göteborg Energi (effekttariff: 135 kr/kW/mån winter, + enkeltariff)
  - Mälarenergi (effekttariff: 59.25 kr/kW/mån, single peak)
  - Jämtkraft (enkeltariff only, 7.5 öre/kWh)
  - SEOM/Sollentuna (effekttariff: 145 kr/kW/mån winter, flat grundavgift)
  - Anpassad (fully editable)

### Heating & weather
- `heating.py` — Temperature-dependent heating model. `HeatingConfig` with h_loss, COP model, elpatron threshold. Supports bergvärme, luftvärmepump, fjärrvärme, direktel. `fit_heating_model()` auto-calibrates against actual consumption data.
- `weather.py` — SMHI weather data integration. 230 active stations across Sweden. Auto-selects nearest station to user's city. Fetches and caches hourly temperature data. `load_temperatures()`, `find_nearest_station()`.
- `smhi_stations.py` — Auto-generated lookup: station ID → (name, lat, lon)

### Data sources
- `elpriser.py` — CLI + price fetching from elprisetjustnu.se (cached in .price_cache/)
- `tibber_source.py` — Tibber GraphQL API (hourly/daily/monthly consumption, prices, seasonal profiles)
- `entsoe_source.py` — ENTSO-E API + EUR/SEK via ECB (frankfurter.app)
- `import_vattenfall.py` — Parse Vattenfall Eldistribution Excel (Serie sheet, column 6 = Summa/dag)
- `import_consumption.py` — Generic CSV consumption import

### App & deployment
- `app.py` — Streamlit web GUI (main user interface, ~1500 lines)
- `Dockerfile` + `docker-compose.yml` — Container deployment
- `.weather_cache/` — Cached SMHI temperature data per station
- `historik_SE3_3ar.csv` — 3 years of SE3 spot prices (2023-2026)

## Critical implementation details

### Simulation strategy (batteri.py simulate())
- Day-ahead scheduling with perfect foresight (prices known at 13:00)
- Multi-cycle: up to 3 charge/discharge cycles per day when spread justifies it
- Minimum 20 öre/kWh absolute spread required to cycle (avoid wear on low-spread days)
- Solar-aware: estimates expected daily solar surplus, reduces grid charging to leave room for free solar
- Priority chain: household load → flex loads (pool) → battery charging → grid export
- Charging power limited by fuse headroom (fuse capacity − household load at that hour)
- `daily_load_override`: when set, provides date+hour specific load (from heating model), overriding seasonal/hourly profiles
- All tariff types simulated automatically — best picked per battery size

### Effekttariff (power demand tariff)
- `EffektTariff` class: charges based on peak kW demand per month
- `_estimate_effekt_savings()` in app.py: compares monthly peak demand WITH vs WITHOUT battery
- Each operator has different measurement rules (top-N peaks from different days, peak hours, night discount)
- Battery peak shaving: discharge during high-load hours to reduce measured peak
- For SEOM/Ellevio customers: this is often the LARGEST savings component (400-900 kr/mån)

### Heating model (heating.py)
- COP model for ground-source: COP = 3.4 + 0.056 × T_outdoor (bergvärme)
- COP model for air-source: COP = 2.8 + 0.08 × T_outdoor (luftvärmepump)
- Fjärrvärme: COP = 99 (essentially no electrical heating cost)
- Direktel: COP = 1.0
- House heat loss: P_heat = h_loss × max(0, 21 − T_outdoor)
- Elpatron engages when thermal demand exceeds hp_max_heat_kw
- Default calibration from energy class (A-G) × house area → h_loss
- Auto-calibration: `fit_heating_model()` uses least-squares fit of actual consumption vs temperature
- Calibrated values (from Tibber 2024+2025 data for reference user):
  - h_loss = 0.160 kW/°C, HP max = 6 kW, DHW = 6 kWh/day, base = 0.68 kW

### Weather data (weather.py)
- SMHI Open Data API, parameter 1 (hourly air temperature), no API key needed
- 230 active stations across Sweden, auto-nearest-station lookup
- Two endpoints merged: corrected-archive (2008−3 months ago) + latest-months (recent ~4 months)
- Timestamps converted UTC → Europe/Stockholm
- Cached per station in .weather_cache/station_{id}.csv
- `SWEDISH_CITIES` dict: 30 cities with coordinates for quick lookup

### Tariffs (tariff.py)
- Peak hours (höglasttid): Jan-Mar + Nov-Dec, weekdays 06-22, excluding Swedish public holidays
- Easter calculated with Anonymous Gregorian algorithm
- Energy tax: 54.88 öre/kWh (43.90 + 25% moms, 2026)
- `GRID_OPERATORS` dict: operator → fuse_fees, tariff types, effekttariff params
- `create_tariffs_for_operator()`: builds tariff objects from operator presets

### Scenario comparison (app.py)
- Simulation results are split by year to show realistic range
- "Normal years" (avg spot < 70 öre) vs "high-price years" (≥ 70 öre)
- Grouped bar chart per battery size per year
- Addresses bias from including extreme periods (e.g., Q1 2026 with 2× normal prices)

### Fuse size comparison (app.py)
- Re-simulates recommended battery at larger fuse sizes
- Shows extra savings vs extra subscription cost
- Particularly valuable for operators with cheap fuse upgrades (SEOM: 25A→35A only +1,395 kr/yr)

## Key design decisions
- **Recommendation-first**: app tells you what to buy, not the other way around
- **All battery sizes simulated**: editable price table with NKON defaults, user can add/remove
- **All tariffs tested**: per battery size, across operator's available tariff types
- **Cashflow is "money in/out"**, not "profit" — language matters for user understanding
- **Monthly view** preferred over daily (bills are monthly)
- **Mortgage perspective**: at 3% over 50 years, even 2×32 kWh is cash-flow positive from day 1
- **Battery alone is profitable**: 32 kWh without solar saves ~4,800 kr/yr on Tidstariff arbitrage alone
- **Solar self-consumption value** only counted when solar is part of investment
- **The battery doesn't save kWh** — it shifts WHEN you buy (cheap night → expensive peak)
- **EV is tidsstyrd last** (car at work during day), pool is flexibel last (solar surplus)
- **Tibber fee**: 49 kr/mån subscription, 0 kr/kWh markup — included in "without" cost baseline
- **Temperature-aware load model**: hour-by-hour heating demand from actual weather → realistic self-consumption decisions

## API keys (not in repo)
- `.entsoe_key` — ENTSO-E transparency platform token
- `.tibber_token` — Tibber personal access token

## Reference: User's actual consumption (Tibber 2024-2025)
| Component | kWh/year | Share | Daily avg |
|---|---|---|---|
| EV charging | 8,500 | 38% | 23 kWh/day |
| Heating + DHW | 7,750 | 35% | 21 kWh/day |
| Active (stove, lamps) | 3,550 | 16% | 9.7 kWh/day |
| Always-on (fridge, etc.) | 2,370 | 11% | 6.5 kWh/day |
| **Total** | **22,200** | | **61 kWh/day** |

## NKON ESS Pro prices (EUR excl. VAT, ~Q1 2025)
- 5.12 kWh: €600, 10.24 kWh: €1177, 16.1 kWh: €1512, 32.15 kWh: €2857
- Max charge/discharge: 15 kW (32 kWh), 11 kW (16 kWh)
- LiFePO4, 8000 cycles, Seplos 300A BMS
- Supports parallel connection (up to 16 units)

## Known issues / future work
- Solar model is simplified (monthly averages, no weather variation)
- No degradation modeling for battery capacity over time
- Tibber hourly data limited to ~30 days via API, monthly goes back ~12 months
- Pool heat pump modeled as constant 3 kW but real heat pumps vary with temperature
- EV daily consumption assumed constant but varies seasonally
- Effekttariff savings estimation is approximate (compares peak with/without, doesn't model real-time peak shaving strategy)
- Grid operator data is manually maintained — rates may change
- **Future project**: real-time battery controller (separate repo) that talks to Tibber API, BMS, EV charger (OCPP/Modbus) for live optimization + grid flexibility rewards
