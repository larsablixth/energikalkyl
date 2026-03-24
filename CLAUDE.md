# CLAUDE.md

## Project: Energikalkyl — El, Sol & Batteri

Swedish electricity investment analysis tool. Answers: "Should I buy a home battery and/or solar panels, and if so, what size?" Simulates profitability based on historical spot prices, real weather data, actual consumption patterns, grid operator tariffs (including effekttariff), and financing via mortgage.

## How to run
```bash
bash setup.sh                           # First time: installs deps, prompts for Tibber token, starts app
streamlit run app.py                    # Web GUI on port 8501 (after setup)
docker compose up                       # Docker (no Python needed)
python elpriser.py batteri --help       # CLI help
```

### Deployed on Streamlit Community Cloud
- Auto-deploys on push to main
- Tibber token entered via UI (no .tibber_token file needed)
- PVGIS solar data works without any API key

### WSL2 / bare Python environment
No system pip/venv: `setup.sh` uses `get-pip.py` + `--user --break-system-packages`.
Deps: `requirements.txt` (streamlit, plotly, requests, fpdf2, openpyxl, entsoe-py, pandas).

### Claude GitHub Actions
`.github/workflows/claude.yml` — active on all repos. Create issue with `claude` label or comment `@claude`.
Requires `ANTHROPIC_API_KEY` secret (set on all 9 repos).

## Architecture overview

The app follows a 6-step flow:
1. **Load data** — Two expanders, both usable simultaneously:
   - Tibber API: consumption profile + auto-fills address, fuse, grid operator, house size, heating type
   - Vattenfall/CSV/JSON: 3+ years hourly consumption data. JSON is standard format (see `consumption_format.py`)
   - Spot prices: auto-syncs date range with loaded consumption data
   - **Session persistence**: loaded data survives page refreshes (stored in `.app_state/`)
2. **Configure setup** — grid operator (8 presets), fuse (simulated as output), solar, loads, heating model
   - **Solar data**: radio selector — PVGIS satellite (default, location-specific), CSV from inverter, or cos³ model. Tibber production auto-fetched if available.
   - Heating: calibrated from energy class OR manual Tibber Insights breakdown OR auto-fit from consumption
   - Calibrated data overrides energy class completely (house size irrelevant when calibrated)
   - EV default: 18-07 window, 30 kWh/day, Smart=True (picks 3 cheapest hours within window)
   - Flex loads: pool (summer) + varmvatten dump (year-round, absorbs remaining solar)
   - **Luft-luft komplement**: optional air-to-air HP (heating above min temp + AC cooling). Model preset: Mitsubishi Hero 2.0 LN25. Auto-registers as flex load to absorb solar surplus.
3. **Investment** — two pricing modes:
   - Specificerade batterier: editable price table (NKON defaults 5-96 kWh), user can add/remove
   - SEK per kWh: enter price/kWh, auto-generates 5-100 kWh sizes, finds optimal for self-consumption
4. **Results** — simulates ALL battery sizes × ALL tariffs × ALL fuse sizes, recommends optimal combo
   - Annualized cost vs savings (same timescale), cumulative cashflow chart
   - Scenario comparison by year (normal vs high-price years)
   - Self-consumption optimization: finds smallest battery for near-zero grid export
   - Luft-luft contribution shown separately (not part of main ROI)
   - Financing: compared over battery lifetime, not loan term
   - PDF bank report with methodology and three future scenarios
5. **Detail view** — monthly breakdown for selected battery
6. **Future scenarios** — Konservativt (1.5x), Sannolikt (2.5x), Hög volatilitet (4.0x)

## Key files

### Core simulation
- `batteri.py` — Battery simulation engine. `BatteryConfig` dataclass, `simulate()` function. Multi-cycle scheduling, solar-aware, fuse headroom-limited. Supports `daily_load_override` for temperature-dependent load profiles. `LoadSchedule` supports smart mode: picks cheapest N hours within availability window, with effekttariff peak penalty.
- `solar.py` — Solar production model. Three-tier: real hourly data → model scaled to real monthly totals → cos³ curve fallback. `SolarConfig` with `real_production` (hourly dict) and `real_monthly_kwh` (monthly scaling). `get_solar_for_slot()` transparently picks best available source.

### Tariffs & grid operators
- `tariff.py` — Grid tariff models: `Tidstariff`, `FastTariff`, `EffektTariff`. `GRID_OPERATORS` dict with presets for:
  - Vattenfall Eldistribution (tidstariff + enkeltariff, no effekttariff for private yet)
  - Ellevio (effekttariff: 81.25 kr/kW/mån, top-3 peaks, 50% night discount)
  - E.ON Energidistribution (tid + enkel)
  - Göteborg Energi (tidsindelad effekttariff: 135 kr/kW/mån winter, 0 kr summer, flat 205 kr/mån fee + enkeltariff)
  - Mälarenergi (effekttariff: 59.25 kr/kW/mån, single peak — NOTE: being removed 2026-07-01)
  - Jämtkraft (enkeltariff only, 7.5 öre/kWh)
  - SEOM/Sollentuna (effekttariff: 145 kr/kW/mån winter, 72.5 kr/kW/mån summer, 2026 fuse fees by category)
  - Anpassad (fully editable)

### Heating & weather
- `heating.py` — Temperature-dependent heating model. `HeatingConfig` with h_loss, COP model, elpatron threshold. Supports bergvärme, luftvärmepump, fjärrvärme, direktel. Optional luft-luft supplement (air-to-air for heating above configurable min temp + AC cooling). `fit_heating_model()` auto-calibrates against actual consumption data.
- `weather.py` — SMHI weather data integration. 230 active stations across Sweden. Auto-selects nearest station to user's city. Fetches and caches hourly temperature data. `load_temperatures()`, `find_nearest_station()`.
- `smhi_stations.py` — Auto-generated lookup: station ID → (name, lat, lon)

### Data sources
- `elpriser.py` — CLI + price fetching from elprisetjustnu.se (cached in .price_cache/)
- `tibber_source.py` — Tibber GraphQL API (hourly/daily/monthly consumption + production, prices, seasonal profiles). `fetch_production()` for solar panel owners.
- `pvgis_source.py` — EU JRC PVGIS API integration. Satellite-based hourly PV production for any location (2005-2023). No API key. Cached in `.pvgis_cache/`. ~32% more accurate than cos³ model for Stockholm.
- `import_solar.py` — CSV parser for solar production data from inverter portals (Huawei FusionSolar, SMA, Fronius, Enphase, generic Swedish CSV). Auto-detects delimiter, decimal separator, column names.
- `entsoe_source.py` — ENTSO-E API + EUR/SEK via ECB (frankfurter.app)
- `import_vattenfall.py` — Parse Vattenfall Eldistribution Excel. Daily (col 7 = Summa/dag) AND hourly (cols L-W = 24 values/day/month). `parse_vattenfall_hourly()` extracts 8,760 records/year.
- `import_consumption.py` — Generic CSV consumption import
- `convert_vattenfall.py` — CLI: Vattenfall Excel → standard JSON
- `convert_eon.py` — CLI: E.ON API → standard JSON
- `convert_csv.py` — CLI: generic Swedish CSV → standard JSON

### App & deployment
- `app.py` — Streamlit web GUI (main user interface, ~2500 lines). Bilingual Swedish/English.
- `translations.py` — i18n module: 150+ strings, `t(key)` lookup, `set_language("en"/"sv")`. **CRITICAL: never use `t` as a variable name in app.py — it shadows the translation function.**
- `app_state.py` — Session persistence across page refreshes (SQLite-free, JSON in `.app_state/`)
- `setup.sh` — First-time setup: installs pip + deps, prompts for Tibber token, starts app
- `.github/workflows/claude.yml` — Claude Code GitHub Action (PR review, @claude, issue implementation)
- `Dockerfile` + `docker-compose.yml` — Container deployment
- `.weather_cache/` — Cached SMHI temperature data per station
- `.pvgis_cache/` — Cached PVGIS satellite solar data per location/config
- `.app_state/` — Persisted session data (consumption, prices, calibration, solar production)
- `historik_SE3_3ar.csv` — 3 years of SE3 spot prices (2023-2026)

## Critical implementation details

### Simulation strategy (batteri.py simulate())
- Day-ahead scheduling with perfect foresight (prices known at 13:00)
- Multi-cycle: up to 3 charge/discharge cycles per day (5 with export arbitrage)
- Minimum 20 öre/kWh absolute spread required to cycle (10 öre for export arbitrage)
- Solar-aware: estimates expected daily solar surplus, reduces grid charging to leave room for free solar
- Priority chain: household load → battery charging → flex loads (pool/varmvatten) → grid export
- IMPORTANT: battery MUST charge before flex loads — flex loads steal solar otherwise (cost 5,000 kr/yr)
- Charging power limited by fuse headroom (fuse capacity − household load at that hour)
- `daily_load_override`: when set, provides date+hour specific load (from heating model), overriding seasonal/hourly profiles
- All tariff types simulated automatically — best picked per battery size
- **Fuse size optimization**: sweeps one size down + user's fuse + up to 3 larger, picks optimal fuse per battery (net of extra subscription cost). Minimum fuse floor based on household peak load (base + all scheduled loads). Deduplicates to show best fuse per battery label.
- **Phase imbalance derating**: `phase_balance_factor=0.7` reduces usable fuse capacity by 30% for 3-phase. Real loads aren't balanced — one phase often carries ~43% instead of 33%. A 3-phase inverter with per-phase compensation can eliminate this derating by actively balancing phases (discharge onto the overloaded phase).
- **Smart scheduled loads**: `LoadSchedule(smart=True, daily_kwh=30)` picks cheapest N hours within availability window each day (prices known day-ahead). Avoids effekttariff peak hours (penalty scaled by kw_factor for night discount). Tidstariff peak/off-peak handled via total_cost_ore().
- **Discharge valuation**: two modes depending on export setting:
  - Zero-export: ALL discharge valued as avoided purchase at full price (spot + grid + tax). This is correct for Swedish hourly net metering.
  - Export enabled: discharge split into self-consumption (full price) + export surplus (spot × factor − fee). Scheduler uses blended value for cycle profitability.
- **Solar curtailment**: in zero-export mode, solar surplus beyond battery + flex load absorption is curtailed (lost), not exported. Accurately reflects real zero-export inverter behavior.
- **Export arbitrage**: `export_arbitrage_kwh` designates surplus capacity for pure grid trading. More aggressive scheduling (5 cycles, 10 öre min spread). Only viable with effekttariff operators with low energy rates (SEOM 5 öre). Tidstariff operators (Vattenfall 76.5 öre peak) make export unprofitable.

### Solar production data (solar.py, pvgis_source.py)
- Three-tier fallback per simulation hour: real hourly → model scaled to real monthly → pure cos³
- **PVGIS**: EU JRC satellite irradiance (SARAH3), hourly W per location/tilt/orientation, 2005-2023
  - API: `re.jrc.ec.europa.eu/api/v5_3/seriescalc`, no key needed, cached in `.pvgis_cache/`
  - Stockholm 10 kWp: ~10,278 kWh/yr (vs cos³ model 7,760 kWh/yr — model is 32% low)
  - Especially conservative in winter/spring: March model 638 kWh vs PVGIS 1,352 kWh (tilted panels)
- **Tibber**: `fetch_production()` hourly + `fetch_daily_production()` for monthly averages
- **CSV import**: `import_solar.py` handles Swedish semicolon/comma + English formats
- Monthly scaling: `_get_solar_scaled()` uses cos³ hourly shape × (real_monthly / model_monthly) ratio
- `SolarConfig.real_production`: dict "YYYY-MM-DD HH:00" → kW, `real_monthly_kwh`: month → kWh

### Effekttariff (power demand tariff)
- `EffektTariff` class: charges based on peak kW demand per month
- `_estimate_effekt_savings()` in app.py: compares monthly peak demand WITH vs WITHOUT battery
- Each operator has different measurement rules (top-N peaks from different days, peak hours, night discount)
- **Seasonal rates**: `low_season_rate` field for operators with different summer/winter effekt rates (e.g. SEOM: 72.5 kr/kW Apr-Oct, 145 kr/kW Nov-Mar). `get_effekt_rate(month)` returns correct rate.
- Battery peak shaving: discharge during high-load hours to reduce measured peak
- For SEOM/Ellevio customers: this is often the LARGEST savings component (400-900 kr/mån)

### Heating model (heating.py)
- COP model for ground-source: COP = 3.4 + 0.056 × T_outdoor (bergvärme — near-constant, brine temp stable year-round)
- COP model for air-source: COP = 2.8 + 0.08 × T_outdoor (luftvärmepump — drops significantly in cold)
- Fjärrvärme: COP = 99 (essentially no electrical heating cost)
- Direktel: COP = 1.0
- House heat loss: P_heat = h_loss × max(0, 21 − T_outdoor)
- Elpatron engages when thermal demand exceeds hp_max_heat_kw
- Default calibration from energy class (A-G) × house area → h_loss
- Auto-calibration: `fit_heating_model()` uses least-squares fit of actual consumption vs temperature
- Calibrated values (from Tibber 2024+2025 data for reference user):
  - h_loss = 0.160 kW/°C, HP max = 6 kW, DHW = 6 kWh/day, base = 0.68 kW

### Air-to-air supplement (heating.py)
- Optional luft-luft VP as complement to primary heating system
- Heating mode: active above configurable min temp (default 1°C), offloads primary system
- Cooling mode (AC): activates above threshold (default 24°C), 0.1 kW/°C cooling demand
- Default model: Mitsubishi Electric Hero 2.0 LN25 (SCOP 5.2, SEER 10.5, A+++)
  - Nominal: 3.2 kW heat, 2.5 kW cool, COP ~4.5 heating / ~4.2 cooling
  - Price: ~30,000 kr inkl installation (23,990 + ~6,000)
  - Drifttemp: -35°C till +31°C
- Auto-registers as flexible load: pre-cool (summer) / pre-heat (spring/autumn) on solar surplus
- ROI shown separately from main battery/solar investment
- Multi-unit batteries charged sequentially (one at a time), max power = single unit limit (15 kW for 32 kWh)

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
- Energy tax: 45.0 öre/kWh (36.0 + 25% moms, 2026 — reduced from 54.88)
- `GRID_OPERATORS` dict: operator → fuse_fees, tariff types, effekttariff params
- `create_tariffs_for_operator()`: builds tariff objects from operator presets

### Scenario comparison (app.py)
- Simulation results are split by year to show realistic range
- "Normal years" (avg spot < 70 öre) vs "high-price years" (≥ 70 öre)
- Grouped bar chart per battery size per year
- Addresses bias from including extreme periods (e.g., Q1 2026 with 2× normal prices)

### Fuse size optimization (app.py)
- Main optimization sweeps fuse sizes (one smaller + user's selection + up to 3 larger) in outer loop
- Minimum fuse floor: must handle household peak load (base + all scheduled loads running simultaneously)
- Each battery label keeps only the fuse size with highest `profit_life` (net of fuse cost delta)
- `net_benefit_yr` = gross savings − extra fuse subscription cost (vs user's selected fuse)
- Can recommend both upgrades and downgrades (e.g. SEOM 16-25A same price tier)
- Fuse comparison section shows pre-computed variants for recommended battery (no re-simulation)
- Fuse dropdown shows yearly fee per size (e.g. "20A — 1 780 kr/år")
- SEOM 2026 fuse fees: 16-25A=1,780 kr/yr (same tier), 35A=3,175, 50A=4,475, 63A=5,445

## Key design decisions
- **Recommendation-first**: app tells you what to buy, not the other way around
- **All battery sizes simulated**: editable price table with NKON defaults, user can add/remove
- **All tariffs tested**: per battery size, across operator's available tariff types
- **Cashflow is "money in/out"**, not "profit" — language matters for user understanding
- **Monthly view** preferred over daily (bills are monthly)
- **Mortgage perspective**: financing section compares over battery LIFETIME, not loan term (50yr mortgage outlives 15yr battery)
- **Battery alone is profitable**: 32 kWh without solar saves ~4,800 kr/yr on Tidstariff arbitrage alone
- **Solar self-consumption value** only counted when solar is part of investment
- **The battery doesn't save kWh** — it shifts WHEN you buy (cheap night → expensive peak)
- **EV is smart-scheduled**: wide availability window (18-07), picks cheapest hours day-ahead. Avoids effekttariff peak hours and tidstariff peak rates automatically. Pool + varmvatten are flexibla laster (solar surplus)
- **Zero-export strategy**: default mode. Varmvatten element (3 kW, no daily cap) + luft-luft (pre-heat/cool) absorb surplus after battery. Solar surplus curtailed if no flex loads available. No export-capable inverter or microproducer registration needed. Export mode available as option with comparison showing it's typically worse than self-consumption.
- **Export comparison**: expandable section in results shows zero-export vs export side by side, with tipping point analysis. Conclusion: export only viable with effekttariff operators (SEOM) and consistently high daily spreads (>60 öre).
- **Session persistence**: consumption data, prices, calibration inputs survive page refreshes (`.app_state/session.json`)
- **Luft-luft is optional and separate**: shown outside main investment ROI, contribution reported as bonus
- **Tibber auto-fill**: one click fetches address, city, grid operator, fuse size, house area, residents, heating type, price area — all auto-configured
- **Tibber Insights calibration**: manual input of annual breakdown (heating/EV/active/always-on) for per-house h_loss fitting
- **Calibrated h_loss overrides energy class**: if consumption data is loaded, calibration runs BEFORE widget renders
- **Three future scenarios**: Konservativt (1.5x), Sannolikt (2.5x), Hög volatilitet (4.0x) — based on analyst consensus
- **PDF bank report**: includes methodology, scenarios, battery comparison, financing analysis

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
- Max charge/discharge: 15 kW (32 kWh), 11 kW (16 kWh) — per unit
- LiFePO4, 8000 cycles, Seplos 300A BMS
- Supports parallel connection (up to 16 units), but charged sequentially in this setup
- Default presets: 5, 10, 16, 32, 32+16, 2x32, 2x32+16, 3x32 kWh
- Alternative pricing: SEK/kWh mode auto-generates 5-100 kWh sizes for self-consumption optimization

## Lessons learned (bugs found and fixed)
- **Battery must charge before flex loads** — flex loads stole 5,000 kr/yr from battery when given priority on solar
- **Calibrated h_loss must override energy class BEFORE widget renders** — Streamlit locks widget defaults on first render
- **ALL defaults must derive from calibration when available** — 270 m² gave HP=10.8 kW (wrong), calibration gives 5.8 kW (correct)
- **EV scheduled_loads must be passed with daily_load_override** — total_load_kw now adds them automatically
- **Financing over battery lifetime, not loan term** — 50yr mortgage makes anything look positive, but battery dies at 15yr
- **Test the actual integration path** — writing PDF to file works, Streamlit download_button needs bytes not bytearray
- **House area is irrelevant when calibrated** — h_loss IS the house, area is only a starting guess
- **Never use `t` as variable in app.py** — shadows translation function. Includes `for hr, t in hourly:` loop unpacking (renamed to `temp_c`)
- **Zero-export discharge must NOT be capped at load_kw** — capping discharge at base_load (2 kW) made 96 kWh batteries unprofitable. Original behavior (full discharge = avoided purchase) is correct for Swedish hourly net metering
- **Export split is separate from zero-export** — zero-export values all discharge as self-consumption. Export mode splits into self-consumption + export at different prices. Mixing the two broke profitability
- **Phase imbalance matters for fuse sizing** — 70% derating for 3-phase. 3× Victron MultiPlus-II with per-phase compensation is the only 48V option that eliminates this
- **Smart load scheduling needs effekttariff penalty** — without it, EV charges during SEOM peak hours (07-19), increasing effektavgift. Penalty scales by kw_factor for Ellevio night discount

## Verified simulation results (2026-03-21)
With correct parameters (20A fuse, 270 m², calibrated h_loss=0.160, EV 23-03):
- 2x32 kWh: 16,821 kr/yr, 7.4 year payback, +128,603 kr over 15 years
- On mortgage (3%, 50yr): +1,003 kr/mån netto
- Battery alone (no solar): still profitable
- All tests pass (10 integration tests + full end-to-end)

## Known issues / future work
- ~~Solar model is simplified~~ — RESOLVED: PVGIS satellite data + Tibber production + CSV import. cos³ fallback only when no real data.
- PVGIS data ends ~early 2023 (SARAH3 database). For 2024+ simulation dates, monthly-scaled model used.
- No degradation modeling for battery capacity over time
- Tibber hourly data limited to ~30 days via API — use Vattenfall Excel for long history
- Pool heat pump modeled as constant 3 kW but real heat pumps vary with temperature
- ~~EV modeled as 11 kW × 23-03~~ — RESOLVED: smart scheduling picks cheapest hours within configurable window (default 18-07, 30 kWh/day). Avoids effekttariff peak hours and tidstariff peak rates.
- Effekttariff savings estimation is approximate (no real-time peak shaving strategy)
- Grid operator tariff data manually maintained in GRID_OPERATORS dict — rates may change
- **Mälarenergi effekttariff removed 2026-07-01** — government withdrew requirement. Code still has it for Jan-Jun 2026 simulations but will need update.
- **Göteborg Energi** has two models: standard (49 kr/kW year-round) and tidsindelad (135 kr/kW winter). Code models tidsindelad. Standard model not yet available as option.
- Vattenfall hourly extraction: some files produce 364 days instead of 365 (Dec 31 missing)
- **RISE Eltariff-API**: open free API for grid tariffs, goal ALL 155 operators by 2027. Should replace hardcoded GRID_OPERATORS. GitHub: RI-SE/Eltariff-API, endpoints at api.goteborgenergi.cloud and api.tekniskaverken.net. Currently: Göteborg Energi, Tekniska verken, E.ON, Vattenfall, Halmstad, Kraftringen.
- **Metry API**: aggregates consumption from 150k+ meters across operators. OAuth2, REST, hourly data. Could replace per-operator integrations. energimolnetapi11.docs.apiary.io
- **Future project**: real-time battery controller (separate repo) — Tibber API + BMS + EV charger (OCPP/Modbus) for live optimization + grid flexibility rewards
