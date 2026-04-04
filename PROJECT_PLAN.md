# Energikalkyl — Complete Project Plan

**Purpose**: This document describes the Energikalkyl project in enough detail to recreate it from scratch. It covers architecture, every module, data structures, algorithms, APIs, UI flow, and deployment.

**What it does**: Swedish household energy investment analysis tool. Answers: *"Should I buy a home battery and/or solar panels, and if so, what size?"* Simulates profitability based on historical spot prices, real weather data, actual consumption patterns, grid operator tariffs (including effekttariff), and financing via mortgage.

**Scale**: ~10,900 lines of Python across 18 modules + 1 test file.

---

## Table of Contents

1. [Tech Stack & Dependencies](#1-tech-stack--dependencies)
2. [Project Structure](#2-project-structure)
3. [Architecture Overview](#3-architecture-overview)
4. [Module 1: Battery Simulation (batteri.py)](#4-module-1-battery-simulation-batteripy)
5. [Module 2: Solar Production (solar.py)](#5-module-2-solar-production-solarpy)
6. [Module 3: Grid Tariffs (tariff.py)](#6-module-3-grid-tariffs-tariffpy)
7. [Module 4: Heating Model (heating.py)](#7-module-4-heating-model-heatingpy)
8. [Module 5: Spot Prices (elpriser.py)](#8-module-5-spot-prices-elpriserpy)
9. [Module 6: Tibber API (tibber_source.py)](#9-module-6-tibber-api-tibber_sourcepy)
10. [Module 7: PVGIS Satellite Solar (pvgis_source.py)](#10-module-7-pvgis-satellite-solar-pvgis_sourcepy)
11. [Module 8: Weather Data (weather.py)](#11-module-8-weather-data-weatherpy)
12. [Module 9: ENTSO-E Prices (entsoe_source.py)](#12-module-9-entso-e-prices-entsoe_sourcepy)
13. [Module 10: E.ON API (eon_source.py)](#13-module-10-eon-api-eon_sourcepy)
14. [Module 11: Import Modules](#14-module-11-import-modules)
15. [Module 12: Streamlit App (app.py)](#15-module-12-streamlit-app-apppy)
16. [Module 13: PDF Report (report.py)](#16-module-13-pdf-report-reportpy)
17. [Module 14: Session Persistence (app_state.py)](#17-module-14-session-persistence-app_statepy)
18. [Module 15: Translations (translations.py)](#18-module-15-translations-translationspy)
19. [Test Suite](#19-test-suite)
20. [Deployment](#20-deployment)
21. [Key Design Decisions](#21-key-design-decisions)
22. [Known Bugs & Lessons Learned](#22-known-bugs--lessons-learned)
23. [Data Flow Diagrams](#23-data-flow-diagrams)
24. [Numeric Constants Reference](#24-numeric-constants-reference)

---

## 1. Tech Stack & Dependencies

**Language**: Python 3.12

**requirements.txt**:
```
requests>=2.28          # HTTP client for all APIs
entsoe-py>=0.7          # ENTSO-E transparency platform client
pandas>=2.0             # DataFrames for price/consumption data
streamlit>=1.30         # Web UI framework
plotly>=5.0             # Interactive charts
openpyxl>=3.1           # Excel parsing (Vattenfall)
fpdf2>=2.7              # PDF report generation
```

**Runtime**: Streamlit server (port 8501), single-process, session-state driven.

---

## 2. Project Structure

```
energikalkyl/
├── app.py                  # 2,815 lines — Streamlit GUI, 6-step flow
├── batteri.py              #   943 lines — Battery simulation engine
├── tibber_source.py        #   630 lines — Tibber GraphQL API
├── elpriser.py             #   527 lines — Spot price fetching
├── tariff.py               #   396 lines — Grid tariff models
├── report.py               #   380 lines — PDF report generation
├── import_vattenfall.py    #   324 lines — Vattenfall Excel parser
├── heating.py              #   286 lines — Temperature-dependent heating model
├── weather.py              #   238 lines — SMHI weather data
├── smhi_stations.py        #   235 lines — Auto-generated station lookup
├── import_consumption.py   #   219 lines — Generic CSV consumption import
├── import_solar.py         #   208 lines — Solar CSV import (multi-portal)
├── solar.py                #   194 lines — Solar production model
├── entsoe_source.py        #   174 lines — ENTSO-E API + EUR/SEK
├── eon_source.py           #   167 lines — E.ON Navigator API
├── pvgis_source.py         #   163 lines — EU JRC PVGIS satellite solar
├── app_state.py            #   115 lines — Session persistence (JSON)
├── translations.py         # 2,274 lines — Bilingual Swedish/English i18n
├── test_energikalkyl.py    #   632 lines — 69 tests (pytest)
├── historik_SE3_3ar.csv    # 3 years of SE3 spot prices (2023-2026)
├── setup.sh                # First-time setup script
├── Dockerfile              # Container build
├── docker-compose.yml      # Container orchestration
├── requirements.txt        # Python dependencies
├── CLAUDE.md               # AI assistant context
├── .github/workflows/
│   └── claude.yml          # Claude Code GitHub Action
├── .price_cache/           # Cached spot prices (per day/zone JSON)
├── .pvgis_cache/           # Cached PVGIS satellite data (per config JSON)
├── .weather_cache/         # Cached SMHI temperature data (per station CSV)
└── .app_state/             # Persisted session data (session.json)
```

---

## 3. Architecture Overview

The app follows a **6-step sequential flow**, all in a single Streamlit page:

```
┌─────────────────────────────────────────────────────────────┐
│  1. LOAD DATA                                                │
│     ├── Tibber API / E.ON API / Vattenfall Excel / CSV       │
│     └── Spot prices (elprisetjustnu.se or CSV)               │
├─────────────────────────────────────────────────────────────┤
│  2. CONFIGURE SYSTEM                                         │
│     ├── Grid operator (8 presets) + fuse size                │
│     ├── Solar panels (PVGIS / Tibber production / CSV / cos³)│
│     ├── Heating model (auto-calibrated from consumption)     │
│     ├── Scheduled loads (EV, pool, DHW — smart scheduling)   │
│     └── Flexible loads (solar surplus absorbers)             │
├─────────────────────────────────────────────────────────────┤
│  3. INVESTMENT                                               │
│     ├── Battery pricing (NKON table or SEK/kWh auto-range)   │
│     ├── Solar costs (material + installation)                │
│     └── Financing (cash / mortgage / loan)                   │
├─────────────────────────────────────────────────────────────┤
│  4. SIMULATE                                                 │
│     └── ALL battery sizes × ALL tariffs × ALL fuse sizes     │
│         → picks optimal combo per battery label              │
├─────────────────────────────────────────────────────────────┤
│  5. RESULTS                                                  │
│     ├── Recommendation (best battery + tariff + fuse)        │
│     ├── Export comparison (zero-export vs grid export)        │
│     ├── Self-consumption optimization                        │
│     ├── PDF bank report + Simulator JSON export              │
│     ├── Scenario split (normal vs high-price years)          │
│     ├── Comparison chart + table                             │
│     ├── Cumulative cashflow (15-year curve)                  │
│     ├── Financing analysis (monthly cost on mortgage)        │
│     └── Fuse comparison (upgrade/downgrade recommendation)   │
├─────────────────────────────────────────────────────────────┤
│  6. DETAIL VIEW + FUTURE SCENARIOS                           │
│     ├── Monthly breakdown for selected battery               │
│     └── 3 scenarios: Conservative/Likely/High volatility     │
└─────────────────────────────────────────────────────────────┘
```

**Data flow**: Raw data → session_state → simulation → results → display/export.

**Key principle**: The app is **recommendation-first** — it tells you what to buy and why, rather than making you pick configurations to test.

---

## 4. Module 1: Battery Simulation (batteri.py)

### 4.1 Data Classes

#### LoadSchedule
Represents a scheduled electrical load (e.g., EV charging).

```python
@dataclass
class LoadSchedule:
    name: str               # e.g., "Elbil"
    power_kw: float         # continuous power when active (e.g., 11.0)
    start_hour: int         # window start (0-23), e.g., 18
    end_hour: int           # window end (0-23), e.g., 7 (wraps midnight)
    daily_kwh: float = 0.0  # energy target/day (0 = run all window hours)
    smart: bool = False     # True: pick cheapest N hours in window
```

**Methods**:
- `is_in_window(hour) → bool` — handles midnight wrap (start=18, end=7 means 18-23 + 0-6)
- `is_active(hour) → bool` — False if smart=True (scheduling done externally)
- `hours_needed() → int` — `ceil(daily_kwh / power_kw)`; 24 if daily_kwh=0

#### FlexibleLoad
Dumpable load that absorbs solar surplus (e.g., DHW tank, pool pump).

```python
@dataclass
class FlexibleLoad:
    name: str
    power_kw: float         # max draw when running (e.g., 3.0)
    daily_kwh: float = 0.0  # daily target (0 = unlimited, runs on surplus)
    start_month: int = 1    # seasonal availability (inclusive, wraps)
    end_month: int = 12
    min_hour: int = 6       # daily availability window
    max_hour: int = 22
```

**Method**: `is_available(month, hour) → bool`

#### BatteryConfig
Complete configuration for battery + household.

```python
@dataclass
class BatteryConfig:
    # Battery
    capacity_kwh: float = 13.5
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    efficiency: float = 0.90          # round-trip
    min_soc: float = 0.05
    max_soc: float = 0.95
    cycle_life: int = 8000
    calendar_life_years: int = 15
    purchase_price: float = 0.0       # SEK
    installation_cost: float = 0.0    # SEK

    # Grid connection
    fuse_amps: float = 25.0
    phases: int = 3
    voltage: float = 230.0
    phase_balance_factor: float = 0.7  # 3-phase derating (one phase carries ~43%)
    fuse_overcurrent_factor: float = 0.0  # IEC 60269 margin

    # Household loads
    base_load_kw: float = 1.5
    scheduled_loads: list[LoadSchedule]
    hourly_load_profile: dict[int, float] | None      # hour → kW
    seasonal_load_profile: dict[int, dict[int, float]] | None  # month → hour → kW
    daily_load_override: dict[str, dict[int, float]] | None    # date → hour → kW
    flexible_loads: list[FlexibleLoad]

    # Export
    export_price_factor: float = 1.0   # fraction of spot received
    export_fee_ore: float = 5.0        # provider fee per exported kWh
    export_arbitrage_kwh: float = 0.0  # reserve for grid trading
```

**Key properties**:
- `grid_max_kw` = effective_amps × voltage × phases / 1000 × phase_balance_factor
  - where effective_amps = fuse_amps × (1 + fuse_overcurrent_factor)
- `usable_kwh` = capacity_kwh × (max_soc − min_soc)
- `total_load_kw(hour, month, date)` — priority: daily_load_override > seasonal > hourly > base + scheduled
- `available_charge_kw(hour, month, date)` = min(max_charge_kw, grid_max_kw − total_load_kw)

#### SlotResult (output per hourly slot)

```python
@dataclass
class SlotResult:
    date: str               # "YYYY-MM-DD"
    hour: str               # "HH:00"
    sek_per_kwh: float      # spot price
    grid_fee_ore: float     # transfer + energy tax
    total_cost_ore: float   # spot + grid fee
    action: str             # "charge" | "discharge" | "idle" | "solar_charge"
    power_kw: float
    energy_kwh: float
    soc_before: float
    soc_after: float
    cost_sek: float         # charging cost
    saving_sek: float       # discharge value (avoided purchase)
    solar_kw: float = 0.0
    solar_charge_kwh: float = 0.0
    flex_consumed_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    export_revenue_sek: float = 0.0
```

#### SimResult

```python
@dataclass
class SimResult:
    config: BatteryConfig
    tariff_name: str = ""
    slots: list[SlotResult]
```

**Computed properties** (aggregations over slots): total_charged_kwh, total_discharged_kwh, total_charge_cost, total_discharge_value, total_solar_charge_kwh, total_flex_consumed_kwh, total_grid_export_kwh, total_export_revenue, net_profit_sek, num_cycles.

### 4.2 Simulation Algorithm

**`simulate(prices, config, tariff=None, solar=None) → SimResult`**

Day-by-day greedy multi-cycle scheduling with perfect day-ahead foresight.

**For each day**:

1. **Smart load pre-scheduling** (if any LoadSchedule has smart=True):
   - For each smart load, find all hours within its availability window
   - Calculate effective cost per hour: `spot + grid_fee + effekttariff_peak_penalty`
   - Peak penalty (effekttariff only): `effekt_rate × kw_factor × load_kw / top_n_peaks / 22`
     - kw_factor = night_discount for hours 22-06, else 1.0
     - Amortized over ~22 weekdays/month
   - Pick cheapest N hours where N = `ceil(daily_kwh / power_kw)`
   - Store in `_smart_schedule[date][load_index] = set(active_hours)`

2. **Solar surplus estimation**: sum expected solar for all daylight hours

3. **Multi-cycle charge/discharge pairing** (up to 3 cycles, 5 if export arbitrage):
   - Calculate per-slot values:
     - Charge cost: `(spot_ore + grid_fee_ore) / 100`
     - Discharge value (blended): `self_frac × total_cost + (1 − self_frac) × export_value`
     - self_frac = load_kw / max_discharge_kw
     - export_value = `spot × export_price_factor − export_fee`
   - For each cycle:
     - Find cheapest available slots to fill battery (leaving room for expected solar)
     - Find matching expensive slots to discharge
     - Check profitability: `avg_discharge_value > avg_charge_cost × (1/efficiency)` AND `absolute_spread > min_spread`
     - min_spread: 20 öre normally, 10 öre for export arbitrage
   - Fallback if no profitable cycles: charge cheapest 25%, discharge most expensive 25%

4. **Per-slot execution** (24 hours):
   - **Step 0**: Solar charges battery (min of surplus, max_charge_kw, available room)
   - **Step 0b**: Flexible loads absorb remaining solar surplus (priority order, respecting daily caps)
   - **Step 0c**: Export remainder to grid OR curtail (zero-export mode)
   - **Step 2**: Grid charge during marked cheap slots (reduced by solar already charging)
   - **Step 3**: Discharge during marked expensive slots
     - Zero-export: all discharge = avoided purchase at full price (spot + grid + tax)
     - Export mode: split into self-consumption + export at different valuations
   - **Idle**: may still have solar charging

**Slot duration detection**: if >24 distinct hours per day → 15-min slots (0.25h), else 60-min (1.0h).

---

## 5. Module 2: Solar Production (solar.py)

### 5.1 SolarConfig

```python
@dataclass
class SolarConfig:
    capacity_kwp: float = 15.0
    orientation: str = "south"
    tilt: float = 35.0                    # degrees
    performance_ratio: float = 0.85       # system losses (inverter, cables, dirt)
    location: str = "Stockholm"
    purchase_price: float = 0.0           # SEK
    installation_cost: float = 0.0
    lifetime_years: int = 25
    degradation_per_year: float = 0.005   # 0.5%/year
    real_production: dict | None = None   # "YYYY-MM-DD HH:00" → kW
    real_monthly_kwh: dict | None = None  # month (1-12) → avg kWh/month
```

### 5.2 Constants

**Monthly production (kWh/kWp, Stockholm south 35° tilt)**:
```python
MONTHLY_KWH_PER_KWP = {
    1: 15,  2: 35,  3: 75,   4: 110,  5: 140,  6: 145,
    7: 140, 8: 115, 9: 75,  10: 40,  11: 15,  12: 8
}  # Total: ~913 kWh/kWp/year
```

**Daylight hours (solar time, mid-month Stockholm)**:
```python
DAYLIGHT_HOURS = {
    1: (8.5, 15.5),  2: (7.5, 16.5),  3: (6.5, 18.0),   4: (5.5, 19.5),
    5: (4.0, 21.0),  6: (3.5, 21.5),  7: (4.0, 21.0),   8: (5.0, 20.0),
    9: (6.5, 18.5), 10: (7.5, 17.0), 11: (8.0, 15.5),  12: (9.0, 15.0)
}
```

### 5.3 Three-Tier Fallback

**`get_solar_for_slot(date_str, hour_str, config) → float (kW)`**:

1. **Real hourly data** (best): lookup `config.real_production["YYYY-MM-DD HH:00"]`
2. **Monthly-scaled model**: cos³ hourly shape × (real_monthly / model_monthly) ratio
3. **Pure cos³ model** (fallback): `MONTHLY_KWH_PER_KWP[month] × capacity × perf_ratio / days × hourly_factor`

**cos³ curve**: For each hour, sample 4 quarter-hour points:
```
angle = (t − solar_noon) / half_daylight × π/2
power = cos³(angle)    # realistic peak concentration
```
Normalize so factors sum to 1.0 per day.

### 5.4 Other Functions

- `estimate_yearly_production(config)` → sum(monthly) × capacity × perf_ratio
- `estimate_lifetime_production(config)` → sum over years with degradation: `yearly × (1 − deg)^year`

---

## 6. Module 3: Grid Tariffs (tariff.py)

### 6.1 Peak Hour Detection

```python
def is_peak_hour(date_str: str, hour_str: str) → bool:
    # Peak if ALL of:
    #   - Month ∈ {1, 2, 3, 11, 12} (winter)
    #   - Weekday (Mon-Fri)
    #   - Hour ∈ [6, 22) (06:00-21:59)
    #   - NOT a Swedish public holiday
```

**Swedish holidays** (computed per year):
- Fixed: Jan 1, Jan 6, Dec 24, Dec 25, Dec 26, Dec 31
- Easter-dependent: Good Friday, Easter Monday
- Easter calculated via **Anonymous Gregorian algorithm**

### 6.2 Fuse Fees (Vattenfall Eldistribution 2026, SEK/year incl. 25% VAT)

```python
FUSE_YEARLY_FEE = {16: 5775, 20: 8085, 25: 10125, 35: 13890, 50: 19945, 63: 26875}
```

### 6.3 Tariff Classes

#### Tidstariff (time-of-use)
```python
@dataclass
class Tidstariff:
    peak: float = 76.50        # öre/kWh during peak hours
    offpeak: float = 30.50     # öre/kWh off-peak
    energy_tax: float = 45.0   # öre/kWh (2026: 36.0 × 1.25 VAT)
    fuse_amps: float = 25.0
    monthly_fee: float | None  # auto from FUSE_YEARLY_FEE
    name: str = "Vattenfall Tidstariff 2026"
```
- `total_cost_ore(d, hour)` = transfer_fee + energy_tax
- `transfer_fee_ore(d, hour)` = peak if is_peak_hour() else offpeak

#### FastTariff (flat rate)
```python
@dataclass
class FastTariff:
    flat_rate: float = 44.50   # öre/kWh constant
    energy_tax: float = 45.0
    fuse_amps: float = 25.0
    monthly_fee: float | None
    name: str = "Vattenfall Enkeltariff 2026"
```

#### EffektTariff (demand charge)
```python
@dataclass
class EffektTariff:
    energy_rate: float = 7.0       # öre/kWh (much lower than tidstariff)
    energy_tax: float = 45.0
    effekt_rate: float = 81.25     # kr/kW/month
    top_n_peaks: int = 3           # avg top-N peaks from different days
    night_discount: float = 0.5    # kW measured at this fraction 22-06
    peak_months: tuple | None      # e.g., (1,2,3,11,12) for winter-only
    low_season_rate: float | None  # effekt_rate for non-peak months
    peak_weekday_only: bool = False
    peak_hour_start: int = 0
    peak_hour_end: int = 24
    fuse_amps: float = 25.0
    monthly_fee: float = 395.0     # abonnemangsavgift
    name: str = "Effekttariff"
```
- `get_effekt_rate(month)` → low_season_rate if month not in peak_months
- `kw_factor(d, hour)` → night_discount for 22-06, else 1.0
- `monthly_demand_cost(peak_kw)` = effekt_rate × peak_kw

### 6.4 Grid Operators (GRID_OPERATORS dict)

| Operator | Tariff types | Effekt rate | Notes |
|---|---|---|---|
| Vattenfall Eldistribution | Tids (76.5/30.5) + Enkel (44.5) | No effekt | Default operator |
| Ellevio | Effekt only | 81.25 kr/kW, top-3, night 50% | All year, no weekday restriction |
| E.ON Energidistribution | Tids (67/22.5) + Enkel (39) | No effekt | Lower rates than Vattenfall |
| Göteborg Energi | Effekt + Enkel (6.5) | 135 kr/kW winter, 0 summer | Weekday 07-20, flat 205 kr/mån fee |
| Mälarenergi | Effekt | 59.25 kr/kW, single peak | Weekday 07-19, **removed 2026-07-01** |
| Jämtkraft | Enkel only (7.5) | None | Cheapest flat rate |
| SEOM (Sollentuna) | Effekt | 145/72.5 kr/kW winter/summer | Top-3, weekday 07-19, same fee 16-25A |
| Anpassad (Custom) | All three | User-editable | Defaults to Vattenfall values |

Each operator also has its own `fuse_fees` dict mapping fuse_amps → SEK/year.

**`create_tariffs_for_operator(operator, fuse_amps, energy_tax) → list[Tariff]`** builds the appropriate tariff objects.

---

## 7. Module 4: Heating Model (heating.py)

### 7.1 HeatingConfig

```python
@dataclass
class HeatingConfig:
    h_loss: float = 0.160          # kW/°C (thermal loss coefficient)
    t_indoor: float = 21.0         # °C setpoint
    cop_base: float = 3.4          # COP at 0°C (ground-source)
    cop_slope: float = 0.056       # COP increase per °C
    cop_min: float = 1.0
    hp_max_heat_kw: float = 6.0    # max heat pump thermal output
    elpatron_kw: float = 3.0       # backup heater (COP=1)
    dhw_kwh_per_day: float = 8.0   # domestic hot water
    dhw_cop: float = 2.3           # DHW COP (higher supply temp)

    # Air-to-air supplement (optional)
    aa_enabled: bool = False
    aa_max_heat_kw: float = 3.2    # Mitsubishi Hero 2.0 LN25
    aa_max_cool_kw: float = 2.5
    aa_cop_heat_base: float = 4.5  # COP at 7°C
    aa_cop_heat_slope: float = 0.1
    aa_cop_cool: float = 4.2
    aa_min_temp: float = 1.0       # min outdoor temp for heating
    aa_cool_threshold: float = 24.0 # indoor temp for cooling activation
```

### 7.2 COP Models

**Ground-source (bergvärme)**:
```
COP = cop_base + cop_slope × T_outdoor = 3.4 + 0.056 × T
```
Near-constant because brine temp is stable year-round.

**Air-source (luftvärmepump)**:
```
COP = 2.8 + 0.08 × T_outdoor
```
Drops significantly in cold weather.

**Air-to-air (luft-luft, supplement)**:
```
COP = aa_cop_heat_base + aa_cop_heat_slope × (T_outdoor − 7.0) = 4.5 + 0.1 × (T − 7)
```
Clamped to ≥ 1.5.

**Fjärrvärme**: COP = 99 (no compressor). **Direktel**: COP = 1.0.

### 7.3 Heating Demand

```
P_heat = h_loss × max(0, T_indoor − T_outdoor)
```

Example: at −10°C → 0.160 × 31 = 4.96 kW thermal demand.

### 7.4 Heating Electricity (main function)

**`heating_electricity_kw(T_outdoor, config) → float (kW electrical)`**:

1. If aa_enabled and T_outdoor ≥ aa_min_temp:
   - Luft-luft handles: `min(demand, aa_max_heat_kw)` at COP_aa
   - remaining_demand decreases
2. Ground-source handles: `min(remaining_demand, hp_max_heat_kw)` at COP_ground
3. Elpatron handles remainder: `min(remaining, elpatron_kw)` at COP=1.0

Returns sum of all electrical draws.

**Cooling** (aa_enabled, T_outdoor > aa_cool_threshold):
```
cooling_demand = min(aa_max_cool_kw, 0.1 × (T_outdoor − threshold))
electricity = cooling_demand / aa_cop_cool
```

### 7.5 Auto-Calibration

**`fit_heating_model(consumption_daily, temps, config) → HeatingConfig`**:

1. **Summer baseline** (T > 15°C): avg consumption on hot days = base + DHW
2. **Base load**: `base_daily = summer_baseline − dhw_kwh_per_day`
3. **Winter fitting** (T < 5°C): for each cold day:
   - `heating_elec = total − base − dhw`
   - `x = 24 × (T_indoor − T_outdoor) / COP(T_outdoor)`
   - Least squares: `h_loss = Σ(x × heating_elec) / Σ(x²)`
4. Returns HeatingConfig with fitted h_loss

### 7.6 Daily Load Profile

**`hourly_consumption_profile(T_hourly, base_load, config) → list[24 floats]`**:

For each hour: `base_load + heating_electricity_kw(T_hour) + dhw_kwh_per_day / 24`

---

## 8. Module 5: Spot Prices (elpriser.py)

### 8.1 API

- **Source**: elprisetjustnu.se (Nord Pool day-ahead prices)
- **Endpoint**: `https://www.elprisetjustnu.se/api/v1/prices/{year}/{MM}-{DD}_{ZONE}.json`
- **Auth**: None
- **Zones**: SE1, SE2, SE3, SE4

### 8.2 Functions

```python
fetch_prices(day: date, zone: str) → list[dict]
    # Single day, disk-cached

fetch_range(start: date, end: date, zone: str, max_workers: int = 20) → list[dict]
    # Date range with 20 concurrent threads + disk cache

save_csv(rows, path)
load_csv(path) → list[dict]
```

### 8.3 Data Format

```python
{
    "date": "YYYY-MM-DD",
    "hour": "HH:MM",
    "zone": "SE3",
    "sek_per_kwh": 0.5234,
    "eur_per_kwh": 0.0454,
    "ore_per_kwh": 52.34
}
```

### 8.4 Caching

- Directory: `.price_cache/`
- Filename: `{YYYY-MM-DD}_{ZONE}.json`
- Persistent across sessions
- Only fetches missing dates on range requests

---

## 9. Module 6: Tibber API (tibber_source.py)

### 9.1 API

- **Endpoint**: `https://api.tibber.com/v1-beta/gql` (GraphQL)
- **Auth**: Bearer token from `TIBBER_TOKEN` env var or `.tibber_token` file
- **Pagination**: 2000 nodes per query batch

### 9.2 Functions

```python
_get_token() → str
_query(query, token) → dict

get_homes(token=None) → list[dict]
    # {id, appNickname, address: {address1, postalCode, city},
    #  currentSubscription: {status}}

fetch_consumption(hours=720, home_id=None, token=None) → list[dict]
    # Hourly: [{from, to, consumption, cost, unitPrice, currency}]

fetch_production(hours=720, home_id=None, token=None) → list[dict]
    # Hourly: [{from, to, production, profit, unitPrice, currency}]

fetch_daily_production(days=1095, home_id=None, token=None) → list[dict]
fetch_daily_consumption(days=1095, home_id=None, token=None) → list[dict]
fetch_monthly_consumption(months=36, home_id=None, token=None) → list[dict]

# Profile builders:
consumption_to_load_profile(nodes) → dict[int, float]  # hour → avg kW
build_seasonal_hourly_profile(hourly, monthly) → dict[int, dict[int, float]]
    # month → hour → kW (scales hourly shape by monthly totals)

production_to_hourly_dict(nodes) → dict[str, float]  # "YYYY-MM-DD HH:00" → kW
production_to_monthly_kwh(nodes) → dict[int, float]  # month → avg kWh/month
```

### 9.3 Home Info (from Tibber)

The app auto-extracts from Tibber:
- Address, city
- Grid company, fuse size (from metering point features)
- House area, number of residents
- Primary heating source (GROUND, AIR2AIR, AIR2WATER, DISTRICT, ELECTRIC)
- Latitude, longitude (for PVGIS)
- Price area (SE1-SE4)
- Solar production (if Pulse connected to panels)

### 9.4 GraphQL Query Structure

```graphql
{
  viewer {
    home(id: "...") {
      consumption(resolution: HOURLY, last: 2000) {
        nodes { from, to, consumption, cost, unitPrice, currency }
      }
      production(resolution: HOURLY, last: 2000) {
        nodes { from, to, production, profit, unitPrice, currency }
      }
      currentSubscription {
        priceInfo {
          today { total, energy, tax, startsAt, level, currency }
          tomorrow { ... }
        }
      }
    }
  }
}
```

---

## 10. Module 7: PVGIS Satellite Solar (pvgis_source.py)

### 10.1 API

- **Source**: EU JRC PVGIS (Photovoltaic Geographical Information System)
- **Endpoint**: `https://re.jrc.ec.europa.eu/api/v5_3/seriescalc`
- **Auth**: None
- **Data**: SARAH3 satellite irradiance, 2005-2023

### 10.2 Functions

```python
fetch_pvgis(lat, lon, peakpower=10.0, loss=14.0, angle=35.0, aspect=0.0,
            startyear=2020, endyear=2023) → list[dict]
    # Returns: [{date, hour, production_kw}]

pvgis_to_hourly_dict(records) → dict[str, float]  # "YYYY-MM-DD HH:00" → kW
pvgis_to_monthly_kwh(records) → dict[int, float]  # month → avg kWh
```

### 10.3 API Parameters

| Parameter | Default | Description |
|---|---|---|
| lat, lon | — | Coordinates |
| peakpower | 10.0 | System size (kWp) |
| loss | 14.0 | System losses % (inverter, cables, dirt) |
| angle | 35.0 | Tilt (0=horizontal, 90=vertical) |
| aspect | 0.0 | Azimuth (0=south, -90=east, 90=west) |
| pvcalculation | 1 | Always 1 |
| outputformat | csv | Response format |
| startyear/endyear | 2020/2023 | Date range |

### 10.4 Response Format

CSV with header, data rows `YYYYMMDDHHMM,watts`, and footer metadata.

### 10.5 Caching

- Directory: `.pvgis_cache/`
- Filename: `pvgis_{lat:.2f}_{lon:.2f}_{peakpower}kWp_{loss}loss_{angle}deg_{aspect}az_{start}-{end}.json`
- Cached as JSON list of records

---

## 11. Module 8: Weather Data (weather.py)

### 11.1 API

- **Source**: SMHI (Swedish Meteorological and Hydrological Institute) Open Data
- **Base URL**: `https://opendata-download-metobs.smhi.se/api/version/1.0/parameter/1`
- **Parameter 1**: Hourly air temperature
- **Auth**: None
- **Two endpoints merged**:
  - Corrected archive: `/station/{id}/period/corrected-archive/data.csv` (2008 to ~3 months ago)
  - Latest months: `/station/{id}/period/latest-months/data.json` (recent ~4 months)

### 11.2 Functions

```python
get_stations() → dict[str, tuple[str, float, float]]
    # station_id → (name, latitude, longitude)
    # Sources from smhi_stations.py (230+ active stations)

find_nearest_station(lat, lon, stations=None) → (station_id, name, distance_km)
    # Haversine distance formula

fetch_station_data(station_id, force=False) → Path
    # Downloads + merges corrected archive + latest months
    # Caches to .weather_cache/station_{id}.csv

load_temperatures(station_id="97400") → dict[str, list[tuple[int, float]]]
    # date → [(hour, temp_c), ...]
    # Default: Stockholm-Arlanda (97400)
```

### 11.3 Built-in Cities

```python
SWEDISH_CITIES = {
    "Stockholm": (59.33, 18.07), "Göteborg": (57.71, 11.97),
    "Malmö": (55.60, 13.00), "Uppsala": (59.86, 17.64),
    "Linköping": (58.41, 15.63), "Örebro": (59.27, 15.21),
    # ... 30 cities total
}
```

### 11.4 Caching

- Per-station CSV: `.weather_cache/station_{id}.csv`
- Columns: date, hour, temp_c
- UTC → Europe/Stockholm timezone conversion
- Data cutoff: Jan 1, 2023 onwards

---

## 12. Module 9: ENTSO-E Prices (entsoe_source.py)

### 12.1 API

- **Client**: entsoe-py library (pandas wrapper)
- **Auth**: API key from transparency.entsoe.eu, stored in `ENTSOE_API_KEY` env or `.entsoe_key`
- **Exchange rates**: frankfurter.app (ECB reference rates)
- **Zone codes**: SE1→SE_1, SE2→SE_2, SE3→SE_3, SE4→SE_4

### 12.2 Functions

```python
fetch_entsoe(start, end, zone) → list[dict]
    # Same format as elpriser.py output
    # Adds eur_sek_rate field

fetch_exchange_rates(start, end) → dict[str, float]
    # "YYYY-MM-DD" → EUR/SEK rate
    # Cached to .fx_cache.json
    # Fallback: 11.5 SEK/EUR
```

**Note**: Nord Pool convention uses ECB rate from (delivery_date − 1), not delivery date.

---

## 13. Module 10: E.ON API (eon_source.py)

### 13.1 API

- **Base URL**: `https://navigator-api.eon.se`
- **Auth**: OAuth2 client credentials (client_id + client_secret)
- **Credentials**: `EON_CLIENT_ID`/`EON_CLIENT_SECRET` env vars or `.eon_credentials` file (format: `client_id:client_secret`)

### 13.2 Functions

```python
_get_credentials() → (client_id, client_secret)
_get_token() → str  # OAuth2 token

get_installations(token=None) → list[dict]
fetch_consumption(installation_id, start_date, end_date,
                  resolution="hour", token=None) → list[dict]
    # Returns: [{date, hour, kwh}]

eon_to_seasonal_profile(hourly_data) → dict[int, dict[int, float]]
```

---

## 14. Module 11: Import Modules

### 14.1 import_vattenfall.py

Parses Vattenfall Eldistribution Excel exports.

**Excel structure**: Sheet "Serie", Row 1=Year, Row 2=Month headers in cols L-W, Row 4+=Data. Col 7=daily sum, Cols 12-23=24 hourly values.

```python
parse_vattenfall_excel(path) → list[dict]       # daily: {date, consumption_kwh}
parse_vattenfall_hourly(path) → list[dict]       # hourly: {date, hour, kwh}
vattenfall_hourly_to_seasonal_profile(data) → dict[int, dict[int, float]]
vattenfall_to_seasonal_profile(daily, hourly_shape) → dict[int, dict[int, float]]
```

Month names mapped: "jan"/"jan."/"januari" → 1, etc.

### 14.2 import_consumption.py

Generic CSV consumption parser with auto-detection.

```python
detect_csv_format(content) → {delimiter, comma_decimal}
parse_consumption_csv(content, filename="") → list[dict]
    # Returns: [{date, hour, consumption_kwh}]
consumption_to_hourly_profile(data) → dict[int, float]   # hour → avg kW
consumption_to_monthly_daily(data) → dict[int, float]     # month → avg kWh/day
```

**Column detection**: looks for Swedish + English column names (datum/date, förbrukning/consumption, tid/time, etc.).

**Encoding fallback**: utf-8 → utf-8-sig → iso-8859-1 → cp1252.

### 14.3 import_solar.py

Solar production CSV parser supporting multiple inverter portals.

```python
parse_solar_csv(content, filename="") → list[dict]
    # Returns: [{date, hour, production_kwh}]
solar_to_hourly_dict(records) → dict[str, float]   # "YYYY-MM-DD HH:00" → kW
solar_to_monthly_kwh(records) → dict[int, float]    # month → avg kWh
```

**Supported formats**: Huawei FusionSolar, SMA Sunny Portal, Fronius Solar.web, Enphase Enlighten, generic Swedish CSV.

---

## 15. Module 12: Streamlit App (app.py)

### 15.1 Initialization (lines 0-100)

```python
import streamlit as st, pandas as pd, plotly.graph_objects as go, json
from datetime import date, timedelta
# ... all module imports ...

st.set_page_config(page_title="Energikalkyl", page_icon="⚡", layout="wide")
```

Language selector at top → `set_language("sv"|"en")`. All UI text via `t("key")`.

**Critical**: Never use `t` as a variable name — it shadows the translation function.

Session state restored from `.app_state/` on startup via `load_state()`.

### 15.2 Step 1: Load Data (lines 104-465)

Two expanders side-by-side:

**Left — Consumption**:
- **Tibber tab**: token input → `fetch_consumption(hours=720)` → seasonal profile + auto-fill all home info. Also fetches solar production if available.
- **E.ON tab**: installation_id + year range → `eon_source.fetch_consumption()` → seasonal profile.
- **File upload**: accepts `.xlsx` (Vattenfall), `.csv` (generic), `.json` (standard format). Multi-file support with deduplication.
- Displays loaded profile: avg daily kWh, date range, hourly distribution chart.

**Right — Prices**:
- **API source**: zone selector (SE1-4, auto-detected from Tibber city), date range (auto-synced to consumption dates), fetch button → `fetch_range()`.
- **CSV upload**: direct price CSV with sek_per_kwh column.
- Displays: date range, average price, daily spread chart (cheapest 4h vs most expensive 4h).

**Spread analysis**: always shown with consumption+prices loaded. Shows monthly avg spread — key indicator of battery viability.

**Session state keys set**: `seasonal_profile`, `hourly_profile`, `vattenfall_hourly`, `tibber_home`, `tibber_solar_hourly`, `tibber_solar_monthly`, `df_prices`.

### 15.3 Step 2: System Configuration (lines 546-1312)

**Grid operator** section:
- Selectbox: 8 operators from `GRID_OPERATORS`
- Fuse size: dropdown with yearly fee per size (from operator's `fuse_fees`)
- Battery efficiency, phases, fuse overcurrent factor

**Solar** section:
- Radio: PVGIS satellite (default) / CSV from inverter / cos³ model
- PVGIS: auto-fetches for Tibber lat/lon, cached in `.pvgis_cache/`
- Tibber production auto-loaded if available
- System size (kWp), tilt, orientation
- Export settings: price factor, fee, arbitrage capacity

**Location & Weather**:
- City selector → `find_nearest_station()` → `load_temperatures()` / `fetch_station_data()`
- Weather station selector (auto-nearest, manual override)
- Temperature data cached per station

**Heating model**:
- House area, energy class (A-G) → initial h_loss estimate
- Heating type: ground-source (COP 3.4), air-source (COP 2.8), district (COP 99), electric (COP 1)
- Parameters: h_loss, hp_max_heat_kw, elpatron_kw, DHW, base_load
- Auto-calibration from consumption data if available (overrides energy class)
- Tibber Insights manual calibration: input annual breakdowns → fit h_loss

**Luft-luft supplement**: checkbox → parameters (default Mitsubishi Hero 2.0 LN25: 3.2kW heat, 2.5kW cool, 30k SEK installed). Shows separate ROI estimate.

**Scheduled loads**: editable list (name, power, window, daily_kwh, smart). Default: EV 11kW 18-07 30kWh smart.

**Flexible loads**: pool pump (summer 3kW), varmvatten element (year-round 3kW no daily cap, absorbs solar).

**Builds**: `heating_config`, `scheduled_loads`, `flexible_loads`, `daily_load_override` (temp-dependent hourly profile), `solar_config`.

### 15.4 Step 3: Investment (lines 1315-1426)

**Pricing mode** radio:
1. **Specificerade batterier**: editable DataFrame table
   - Default NKON ESS Pro prices (5-96 kWh), user can add/remove rows
   - Columns: Namn, Kapacitet_kWh, Max_kW, Pris_SEK
   - EUR→SEK exchange rate input
2. **SEK per kWh**: price/kWh input → auto-generates 5-100 kWh range in 5 kWh steps

**Installation costs**: battery install (SEK), solar material (SEK), solar install (SEK).

**Financing**: cash / mortgage (rate %, term years) / loan (rate %, term years).

### 15.5 Step 4: Simulation (lines 1428-1712)

**Fuse sweep**: [fuse−1 size, user's fuse, fuse+1, fuse+2, fuse+3] (bounded by operator's fee table).
**Minimum fuse floor**: must handle peak_load = base + all scheduled loads simultaneously.

**Triple nested loop**:
```
for fuse in fuse_sweep:
    tariffs = create_tariffs_for_operator(operator, fuse)
    for battery in battery_table:
        for tariff in tariffs:
            result = simulate(prices, config, tariff, solar)
            savings = arbitrage + solar_self_consumption + effekttariff_peak_shaving
            → record {label, capacity, invest, benefit_yr, payback, profit_life, ...}
```

**Effekttariff savings** estimated by: comparing monthly peak demand WITH vs WITHOUT battery (peak shaving).

**Deduplication**: per battery label, keep only the (fuse, tariff) combo with highest `profit_life`.

**Session state set**: `all_results`, `solar_cfg`, `price_rows`, `fuse_variants`, `shared_config`.

### 15.6 Step 5: Results (lines 1713-2811)

**Sections in order**:

1. **Recommendation**: best battery by lifetime profit. Shows: label, fuse, annual/monthly benefit, invest, payback, lifetime profit.

2. **Export comparison** (expandable): zero-export vs grid export side-by-side. Tipping point analysis.

3. **Self-consumption optimization** (SEK/kWh mode): smallest battery for near-zero grid export.

4. **Luft-luft contribution**: separate ROI if aa_enabled.

5. **PDF report**: `generate_report(...)` → `st.download_button()`.

6. **Simulator JSON export**: `_build_simulator_export()` → JSON with consumption, prices, weather, solar, calibration, location, zone.

7. **Scenario split**: results by year. "Normal" (avg spot < 70 öre) vs "high-price" (≥ 70 öre). Grouped bar chart.

8. **Comparison chart**: annualized cost vs savings bar chart. Comparison table with all batteries.

9. **Cumulative cashflow**: 15-year investment curve (Plotly line chart).

10. **Financing**: monthly cashflow on mortgage. Monthly loan cost vs monthly savings.

11. **Fuse comparison**: pre-computed variants for recommended battery. Shows: fuse → savings → net benefit.

12. **Detail view**: monthly breakdown for user-selected battery. Month-by-month cost/savings table + chart.

13. **Future scenarios**: 3 volatility multipliers applied to price spreads:
    - Konservativt: 1.5× (mild increase)
    - Sannolikt: 2.5× (analyst consensus)
    - Hög volatilitet: 4.0× (energy crisis)

### 15.7 Session State Keys (comprehensive)

| Key | Type | Set by |
|---|---|---|
| `seasonal_profile` | dict[int, dict[int, float]] | Tibber/Vattenfall/CSV |
| `hourly_profile` | dict[int, float] | Tibber/CSV |
| `vattenfall_hourly` | list[dict] | Vattenfall Excel |
| `tibber_home` | dict | Tibber API |
| `tibber_solar_hourly` | dict[str, float] | Tibber/PVGIS/CSV |
| `tibber_solar_monthly` | dict[int, float] | Tibber/PVGIS/CSV |
| `df_prices` | DataFrame | elpriser/CSV |
| `price_rows` | list[dict] | Simulation input |
| `all_results` | list[dict] | Simulation output |
| `solar_cfg` | SolarConfig | Step 2 |
| `shared_config` | BatteryConfig | First result's config |
| `fuse_variants` | dict[str, list[dict]] | Simulation |
| `scheduled_loads` | list[dict] | Step 2 UI |
| `use_aa` | bool | Step 2 UI |
| `app_language` | str | Language selector |
| `scenario_results` | dict | Future scenarios |

---

## 16. Module 13: PDF Report (report.py)

### 16.1 Class

```python
class EnergiReport(FPDF):
    # Custom PDF with header/footer
    # Swedish-language investment report
```

### 16.2 Function

```python
generate_report(
    address, grid_operator, fuse_amps, solar_kwp,
    battery_label, capacity_kwh, price_sek, install_cost,
    savings_per_year, payback_years, lifetime_years, lifetime_profit,
    cycles_per_year, best_tariff,
    loan_rate, loan_years, monthly_loan_cost, monthly_net,
    price_data_range, price_data_days, weather_station,
    all_results,           # list of dicts for comparison table
    future_scenarios=None  # dict with 3 scenario results
) → bytes (PDF content)
```

### 16.3 Sections

1. **Sammanfattning** — executive overview
2. **Fastighet och elanläggning** — property, grid, fuse, tariff, solar
3. **Investering** — cost breakdown
4. **Kassaflödesanalys** — yearly savings, payback, lifetime, financing
5. **Scenariokänslighet** — normal vs high-price years
6. **Framtidsprognos** — 3 volatility scenarios
7. **Jämförelse batteristorlekar** — all sizes table
8. **Metod och antaganden** — methodology
9. **Antaganden och risker** — disclaimer

---

## 17. Module 14: Session Persistence (app_state.py)

### 17.1 Functions

```python
save_state(session_state)
    # Saves to .app_state/session.json
    # Converts: DataFrame → {_type: "dataframe", records: [...]}
    # Converts: dict with int keys → str keys

load_state(session_state)
    # Restores from .app_state/session.json
    # Only sets missing keys (doesn't overwrite current)
    # Converts back: str keys → int for profiles
```

### 17.2 Persisted Keys

Consumption (seasonal_profile, hourly_profile, vattenfall_hourly), prices (df_prices as records), house info (tibber_home), calibration inputs (cal_year, cal_total, cal_heating, cal_ev, cal_active, cal_always), solar data (tibber_solar_hourly, tibber_solar_monthly), air-to-air settings.

---

## 18. Module 15: Translations (translations.py)

### 18.1 Structure

```python
_lang = "sv"

STRINGS = {
    "key": {"sv": "Swedish text", "en": "English text"},
    # 1000+ keys
}

def t(key) → str:   # returns translated string
def set_language(lang): ...
def get_language() → str: ...
```

### 18.2 Categories (~1000+ keys)

- App title/subtitle (4)
- Step 1: Load data — Tibber, E.ON, file upload, prices (40+)
- Step 2: System — heating, solar, loads, locations (50+)
- Step 3: Investment — battery pricing, financing (30+)
- Step 4: Simulation — progress, buttons (20+)
- Results — recommendation, charts, scenarios (100+)
- PDF/Export (20+)
- Errors/Info messages (50+)

---

## 19. Test Suite

**File**: `test_energikalkyl.py` (632 lines, 69 tests)

**Run**: `python -m pytest test_energikalkyl.py -v`

**Coverage**:
- **tariff.py**: Swedish holidays (fixed + Easter), peak hour detection (winter weekday, summer, weekend, holiday), Tidstariff/FastTariff/EffektTariff calculations, grid operator presets, fuse fees
- **heating.py**: COP models (ground, air, air-to-air), heating demand, air-to-air logic, cooling, fit_heating_model
- **solar.py**: hourly factors (sum to 1, peak at noon, zero at night), real data override, monthly scaling, yearly/lifetime production
- **batteri.py**: LoadSchedule (window wrap, smart mode, hours_needed), FlexibleLoad (seasonal availability), BatteryConfig (grid_max_kw, usable_kwh, total_load_kw, fuse analysis), simulate() with flat/tids/effekt tariffs

---

## 20. Deployment

### 20.1 Local (WSL2 / bare Python)

```bash
bash setup.sh
# Installs pip (if missing) via get-pip.py
# pip install --user --break-system-packages -r requirements.txt
# Prompts for Tibber token → .tibber_token
# streamlit run app.py --server.headless true
```

### 20.2 Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY historik_SE3_3ar.csv ./
COPY .weather_cache/ .weather_cache/
# Streamlit config: headless, port 8501, no CORS, no telemetry
EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

```yaml
# docker-compose.yml
services:
  energikalkyl:
    build: .
    ports: ["8501:8501"]
    volumes:
      - ./.tibber_token:/app/.tibber_token:ro
      - ./.entsoe_key:/app/.entsoe_key:ro
      - ./.price_cache:/app/.price_cache
```

### 20.3 Streamlit Community Cloud

- Auto-deploys on push to `main`
- Tibber token entered via UI (no `.tibber_token` file needed)
- PVGIS solar data works without any API key

### 20.4 GitHub Actions

```yaml
# .github/workflows/claude.yml
name: Claude Code
on:
  issue_comment: [created]
  pull_request_review_comment: [created]
  pull_request: [opened, synchronize]
  issues: [opened, labeled]
permissions: {contents: write, pull-requests: write, issues: write}
jobs:
  claude:
    runs-on: ubuntu-latest
    if: contains(comment.body, '@claude') || labeled('claude') || PR
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          claude_args: "--max-turns 10"
```

---

## 21. Key Design Decisions

1. **Recommendation-first**: app tells you what to buy, not the other way around.
2. **All sizes × all tariffs × all fuses simulated**: exhaustive search for optimal combo.
3. **Cashflow language**: "money in/out" not "profit" — user understanding matters.
4. **Monthly view**: bills are monthly, so savings shown monthly.
5. **Mortgage perspective**: financing compared over battery LIFETIME (15 yr), not loan term (50 yr).
6. **Battery alone is profitable**: 32 kWh without solar saves ~4,800 kr/yr on arbitrage alone.
7. **Solar self-consumption**: only counted when solar is part of investment.
8. **Battery doesn't save kWh**: it shifts WHEN you buy (cheap night → expensive peak).
9. **Zero-export default**: varmvatten + luft-luft absorb surplus. No export registration needed.
10. **Battery charges before flex loads**: flex loads steal solar otherwise (5,000 kr/yr bug found).
11. **Calibrated h_loss overrides energy class**: house area becomes irrelevant when real data exists.
12. **Smart EV scheduling**: picks cheapest hours day-ahead, avoids effekttariff peaks.
13. **Phase imbalance derating**: 70% for 3-phase (real loads aren't balanced).
14. **Luft-luft is separate**: shown outside main ROI as bonus.
15. **Tibber auto-fill**: one click configures everything.
16. **Three future scenarios**: Conservative (1.5×), Likely (2.5×), High volatility (4.0×).

---

## 22. Known Bugs & Lessons Learned

1. **Battery must charge before flex loads** — flex loads stole 5,000 kr/yr from battery.
2. **Calibrated h_loss must override BEFORE widget renders** — Streamlit locks defaults on first render.
3. **ALL defaults derive from calibration when available** — 270 m² gave HP=10.8 kW (wrong), calibration gives 5.8 kW.
4. **EV scheduled_loads must be passed with daily_load_override** — total_load_kw adds them automatically.
5. **Financing over battery lifetime, not loan term** — 50yr mortgage makes anything look positive.
6. **PDF needs bytes not bytearray** — Streamlit download_button difference.
7. **Never use `t` as variable** — shadows translation function. Includes loop unpacking.
8. **Zero-export discharge must NOT be capped at load_kw** — capping made 96 kWh batteries unprofitable.
9. **Export split is separate from zero-export** — mixing the two broke profitability.
10. **Smart load scheduling needs effekttariff penalty** — without it, EV charges during peak hours.

---

## 23. Data Flow Diagrams

### Price Data
```
elprisetjustnu.se API → fetch_range() → .price_cache/ → DataFrame
                                                         ↓
                                          price_rows list[dict] → simulate()
```

### Consumption Data
```
Tibber API ──→ consumption_to_load_profile() ──→ hourly_profile
           └→ build_seasonal_hourly_profile() ─→ seasonal_profile
Vattenfall ──→ parse_vattenfall_hourly() ──────→ vattenfall_hourly
           └→ vattenfall_hourly_to_seasonal() ─→ seasonal_profile
CSV ─────────→ parse_consumption_csv() ────────→ hourly_profile + seasonal_profile
```

### Solar Data
```
PVGIS API ──→ pvgis_to_hourly_dict() ──→ tibber_solar_hourly
           └→ pvgis_to_monthly_kwh() ──→ tibber_solar_monthly
Tibber ─────→ production_to_hourly_dict() → tibber_solar_hourly
CSV ────────→ solar_to_hourly_dict() ──→ tibber_solar_hourly
                    ↓
              SolarConfig.real_production / real_monthly_kwh
                    ↓
              get_solar_for_slot() → kW per simulation hour
```

### Weather → Heating → Load
```
SMHI API → .weather_cache/ → load_temperatures()
                              ↓
              temps_data: {date: [(hour, temp_c)]}
                              ↓
              heating_electricity_kw() per hour
                              ↓
              daily_load_override: {date: {hour: total_kW}}
                              ↓
              BatteryConfig.total_load_kw() in simulate()
```

### Simulation → Results
```
simulate(prices, config, tariff, solar) → SimResult
    ↓
all_results = [{label, capacity, invest, benefit_yr, payback, profit_life, ...}]
    ↓
├── Recommendation (best by profit_life)
├── Charts (Plotly bar, line, table)
├── PDF report (generate_report())
├── JSON export (_build_simulator_export())
└── Future scenarios (re-simulate with scaled spreads)
```

---

## 24. Numeric Constants Reference

### Energy & Grid
| Constant | Value | Source |
|---|---|---|
| Energy tax (2026) | 45.0 öre/kWh | 36.0 öre × 1.25 VAT |
| Vattenfall peak rate | 76.5 öre/kWh | 2026 tariff |
| Vattenfall off-peak | 30.5 öre/kWh | 2026 tariff |
| Vattenfall flat rate | 44.5 öre/kWh | 2026 tariff |
| Peak hours | 06-22 weekdays | Jan-Mar + Nov-Dec |
| Min cycle spread | 20 öre/kWh | Simulation threshold |
| Min export spread | 10 öre/kWh | More aggressive |

### Battery (NKON ESS Pro)
| Capacity | EUR (excl. VAT) | Max kW |
|---|---|---|
| 5.12 kWh | €600 | 5 |
| 10.24 kWh | €1,177 | 11 |
| 16.1 kWh | €1,512 | 11 |
| 32.15 kWh | €2,857 | 15 |
| LiFePO4, 8000 cycles, Seplos 300A BMS | | |

### Heating
| Parameter | Ground-source | Air-source | Air-to-air | District | Electric |
|---|---|---|---|---|---|
| COP base | 3.4 | 2.8 | 4.5 (at 7°C) | 99 | 1.0 |
| COP slope | 0.056/°C | 0.08/°C | 0.1/°C | 0 | 0 |
| Calibrated h_loss | 0.160 kW/°C | | | | |
| DHW | 8 kWh/day | | | | |
| DHW COP | 2.3 | | | | |

### Solar
| Parameter | Value |
|---|---|
| Annual yield (Stockholm, south 35°) | ~913 kWh/kWp (cos³) or ~1,028 kWh/kWp (PVGIS) |
| Performance ratio | 0.85 |
| Degradation | 0.5%/year |
| Panel lifetime | 25 years |
| PVGIS vs cos³ difference | PVGIS is ~32% higher (more accurate) |

### Reference Household (from Tibber 2024-2025)
| Component | kWh/year | Share | Daily avg |
|---|---|---|---|
| EV charging | 8,500 | 38% | 23 kWh/day |
| Heating + DHW | 7,750 | 35% | 21 kWh/day |
| Active (stove, lamps) | 3,550 | 16% | 9.7 kWh/day |
| Always-on (fridge, etc.) | 2,370 | 11% | 6.5 kWh/day |
| **Total** | **22,200** | | **61 kWh/day** |

### Verified Results (2026-03-21, 20A fuse, calibrated)
- 2×32 kWh: 16,821 kr/yr, 7.4 year payback, +128,603 kr over 15 years
- On mortgage (3%, 50yr): +1,003 kr/mån netto

---

*Generated 2026-04-02. This plan reflects the codebase at commit 62989eb.*
