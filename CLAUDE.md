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

## Architecture overview

The app follows a 6-step flow:
1. **Load data** — Two expanders, both usable simultaneously:
   - Tibber API: consumption profile + auto-fills address, fuse, grid operator, house size, heating type
   - Vattenfall/CSV/JSON: 3+ years hourly consumption data. JSON is standard format (see `consumption_format.py`)
   - Spot prices: auto-syncs date range with loaded consumption data
   - **Session persistence**: opt-in only (`ENERGIKALKYL_PERSIST=1`, self-hosted). Off on the public deployment: one shared file leaked data between visitors
2. **Configure setup** — grid operator (8 presets), fuse (simulated as output), solar, loads, heating model
   - **Current tariff** ("Din nuvarande tariff", only for operators with several tariffs, default "Vet inte"): doesn't change the simulation. The result shows what switching alone saves (`tariff_switch_saving`: current tariff's `baseline_bill` − cheapest) and switch + investment vs today. Like the fuse downgrade tip, the switch saving is never counted in the investment result
   - **Solar data**: radio selector — PVGIS satellite (default, location-specific), CSV from inverter, or cos³ model. Tibber production auto-fetched if available.
   - Heating: calibrated from energy class OR manual Tibber Insights breakdown OR auto-fit from consumption
   - Calibrated data overrides energy class completely (house size irrelevant when calibrated)
   - Scheduled loads: none by default. "+ Elbil" adds the EV template (`example_inputs.EV_LOAD`: 11 kW, 18-07 window, 30 kWh/day, Smart=True — picks the cheapest hours within the window)
   - Flex loads: only the varmvatten dump by default (year-round, 10 kWh/day ≈ a 300-litre tank; absorbs remaining solar). "+ Poolvärmepump" adds a pool heat pump (3 kW, 20 kWh/day, May-Sep). A pool *heat pump* heats and can wait for surplus; a pool *circulation pump* (0.3-1 kW) runs every day and belongs under scheduled loads or the base load
   - Battery column: efficiency, cycle life, capacity fade (%/yr, default 1.0), standby power inverter + BMS (W, default 45)
   - **Luft-luft komplement**: optional air-to-air HP (heating above min temp + AC cooling). Model preset: Mitsubishi Hero 2.0 LN25. Auto-registers as flex load to absorb solar surplus.
3. **Investment** — two pricing modes:
   - Specificerade batterier: editable price table (NKON defaults 5-96 kWh), user can add/remove
   - SEK per kWh: enter price/kWh, auto-generates 5-100 kWh sizes, finds optimal for self-consumption
4. **Results** — simulates ALL battery sizes × ALL tariffs × ALL fuse sizes, recommends optimal combo
   - Progress bar (`_SimProgress`) while it runs: one step per simulation (battery × tariff × fuse) + the future-scenario simulations; shows the battery/fuse/tariff being simulated, n/total and time left (from the simulations done so far). A run takes ~23 s locally (70 steps, some reused, ~0.3 s per simulation), ~30 s on Streamlit Cloud
   - "Assumptions behind this result" block (always visible) right under the recommendation: also grid operator/fuse/phases, the reference tariff and the consumption source; untouched example figures are marked
   - "Exempelkalkyl" warning under the recommendation listing personal figures still at their example values (also first in the PDF summary)
   - Annualized cost vs lifetime-average savings (same timescale), cumulative cashflow chart (stops at battery lifetime)
   - Scenario comparison by year (normal vs high-price years)
   - Self-consumption optimization: finds smallest battery for near-zero grid export
   - Luft-luft contribution shown separately (not part of main ROI)
   - Financing: compared over battery lifetime, not loan term
   - PDF bank report with methodology, wear/standby assumptions and five future scenarios
   - **Controller check** ("Klarar ett riktigt styrsystem det här?", on request): the NORVI's own controller (firmware `controller.cpp`, copied into `controller/` with the simulator's period runner `sim/runner.cpp` + world, compiled with g++ into `.controller_build/`, run as a subprocess) runs the recommended battery's period (`controller_check.calculator_hourly`) minute by minute: 13:30 price fetch, its own load/solar forecast (the weather station's hourly °C plays SMHI's forecast: the controller plans the house from it and learns the house, as on site; without °C it never learns and plans the reference house — the example house was −21 % instead of −7 %), ≤ 6-point Deye program, EV + fuse budget, look-ahead, fuse guard. Installation set at run time (firmware `plant.h`): battery, fuse, EV kWh/day from the calculator's EV, solar kWp, grid fees from the calculator's buying cost. Steps: parity (≈ 0) → Deye program → the real controller; plus EV charging cost; the total is applied to year-1 benefit. Zero export only. Not in the PDF. Same runner as energy-scheduler-sim's "Validate calculator" / `make validate`. Reference data (3 yr, Vattenfall Tid, 25 A, EV 20 kWh/day, 10 kWp, Stockholm °C): 32 kWh −4.3 %, 64 kWh −4.6 %, ~8 s
5. **Detail view** — monthly breakdown for selected battery; where the solar production goes (direct, battery, flex, export, curtailed)
   - **Energy flows** ("Så flödar energin"): Sankey of an average year (sun/grid/battery → house/EV/battery/flex/export/curtailed/losses, `controller_check.energy_flows`) and an hour-by-hour day chart (`day_flows`; default = the day the battery delivered most). House/EV split by the EV's share of each hour's load. Colours: one per entity (`FLOW_COLORS`, dataviz reference palette)
   - **Playback** ("Spela upp hela perioden"): `flow_player.player_html()` — a self-contained HTML/JS player in `st.components.v1.html` (runs in the browser, no reruns): bus diagram sun/grid/battery → house/EV/flex, play/pause, speed 1 h/s … 1 month/s (frames average the hours they cover), slider over the whole period, running totals (battery kr, solar used, bought, curtailed). Data = `controller_check.flow_series()` packed as int16 hundredths in base64 (3 years ≈ 0.9 MB). Theme from `st.context.theme`
6. **Future scenarios** — five assumed price-swing levels, named for what they assume (not how likely): Mindre prissvängningar (0.7x), Oförändrat (1.0x, = main result), Något större (1.5x), Mycket större (2.5x), Extremt större (4x)
   - "Sälja eller använda själv": on request, the same scenarios with the opposite export setting (`_compute_export_vol_benefits`, 7 extra simulations, cached as `export_vol_cmp`). Same settings as the results' export comparison (full spot − 5 öre, no arbitrage reserve); its 1.0x row equals that comparison. Lifetime and solar part held at the 1.0x values, like the main scenarios. Scaled prices are clamped ≥ 0, so negative prices are missing (slightly favours export)

## Key files

### Core simulation
- `batteri.py` — Battery simulation engine. `BatteryConfig` dataclass, `simulate()` function. Multi-cycle scheduling, solar-aware, fuse headroom-limited. Supports `daily_load_override` for temperature-dependent load profiles. `LoadSchedule` supports smart mode: picks cheapest N hours within availability window, with effekttariff peak penalty.
- `economics.py` — Pure (no Streamlit) evaluation of simulation results, called by app.py: `solar_direct_use()`, `solar_flows()`, `effekt_savings()`, `baseline_bill()` (household bill without investing, per tariff), `baseline_export_revenue()`, `standby_cost_per_year()`, `yearly_benefit()`, `lifetime_benefit()`, `payback_years()`, `value_at_level()`/`scenario_bat_part()` (future scenarios), `loan_schedule()`. Tested in `test_energikalkyl.py`.
- `flow_player.py` — the energy-flow playback page (HTML/JS template + data packing), shown in the detail view
- `controller_check.py` — Pure (no Streamlit): `calculator_hourly()` (hourly values of a battery result, also used by the simulator export), controller check (`build_binary`, `run_check`, `summarize`) and energy flows (`energy_flows`, `day_flows`). `controller/`: firmware controller copy + simulator runner (`sim/`) + `check_main.cpp`, refreshed with `controller/sync.sh <firmware> <simulator>`. Tested in `test_energikalkyl.py` (needs g++)
- `example_inputs.py` — The example personal figures (battery price table, installation, solar size/price, house) the widgets start with, load templates (EV, pool heat pump, hot water), and `untouched_examples()` which lists those still unchanged in a simulation snapshot. Tested in `test_energikalkyl.py`.
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
  - `parse_any_consumption_file(name, bytes)`: one entry point for uploads (CSV/TXT/TSV/XLSX/JSON; long, wide 24/96-column, meter readings, Wh/kWh, UTC→local, Home Assistant history/statistics). Grid-company layouts other than Vattenfall are generic/assumed until real sample files are collected
- `convert_vattenfall.py` — CLI: Vattenfall Excel → standard JSON
- `convert_eon.py` — CLI: E.ON API → standard JSON
- `convert_csv.py` — CLI: generic Swedish CSV → standard JSON

### App & deployment
- `app.py` — Streamlit web GUI (main user interface, ~2500 lines). Bilingual Swedish/English.
- `translations.py` — i18n module: 150+ strings, `t(key)` lookup, `set_language("en"/"sv")`. **CRITICAL: never use `t` as a variable name in app.py — it shadows the translation function.**
- `app_state.py` — Optional session persistence (JSON in `.app_state/`), only when `ENERGIKALKYL_PERSIST=1`
- `setup.sh` — First-time setup: installs pip + deps, prompts for Tibber token, starts app
- `Dockerfile` + `docker-compose.yml` — Container deployment
- `.weather_cache/` — Cached SMHI temperature data per station
- `.pvgis_cache/` — Cached PVGIS satellite solar data per location/config
- `.app_state/` — Persisted session data (consumption, prices, calibration, solar production)
- `historik_SE3_3ar.csv` — 3 years of SE3 spot prices (2023-2026)

## Critical implementation details

### Simulation strategy (batteri.py simulate())
- Day-ahead scheduling with perfect foresight (prices known at 13:00)
- Daily plan in time order: charge->later-discharge pairs taken most profitable first, only if the battery can hold the energy in between; discharge split into own-load tranche (full price) and export tranche. No trading when the spread doesn't cover efficiency loss + 20 öre (10 with export arbitrage)
- Prices are averaged to hourly (`to_hourly`) before simulating: quarter-hour prices since 2025-10-01
- Spot prices are excl. VAT; buying adds 25% (`spot_vat_factor`), export is paid without VAT
- Minimum 20 öre/kWh absolute spread required to cycle (10 öre for export arbitrage)
- Solar-aware: estimates expected daily solar surplus, reduces grid charging to leave room for free solar
- Priority chain: household load → battery charging → flex loads (poolvärmepump/varmvatten) → grid export
- IMPORTANT: battery MUST charge before flex loads — flex loads steal solar otherwise (cost 5,000 kr/yr)
- Charging power limited by fuse headroom (fuse capacity − household load at that hour)
- `daily_load_override`: when set, provides date+hour specific load (from heating model), overriding seasonal/hourly profiles
- All tariff types simulated automatically. The choice per battery size is made on the whole bill: battery value + counted solar value − `tariff_switch_cost_yr` (the tariff's `baseline_bill` minus the cheapest of the operator's tariffs without investing)
- **Fuse size optimization**: sweeps the user's fuse + up to 3 larger (never smaller, see below), picks optimal fuse per battery (net of extra subscription cost). A larger fuse reuses the smaller fuse's simulation (and its smart-load schedule) when the smaller one never limits charging (grid max ≥ battery max kW + house peak + all scheduled loads): the fuse only enters `simulate()` through the charging room, so the result is identical (`TestFuseReuse`); ~1/3 fewer simulations for the example house. Minimum fuse floor based on household peak load (highest hourly load of the heating model / measured profile, else base load, + all scheduled loads). Deduplicates to show best fuse per battery label.
- **Phase imbalance derating**: `phase_balance_factor=0.7` reduces usable fuse capacity by 30% for 3-phase. Real loads aren't balanced — one phase often carries ~43% instead of 33%. A 3-phase inverter with per-phase compensation can eliminate this derating by actively balancing phases (discharge onto the overloaded phase).
- **Smart scheduled loads**: `LoadSchedule(smart=True, daily_kwh=30)` picks cheapest N hours within availability window each day (prices known day-ahead). Avoids effekttariff peak hours (penalty scaled by kw_factor for night discount). Tidstariff peak/off-peak handled via total_cost_ore().
- **Discharge valuation**: two modes depending on export setting:
  - Zero-export: discharge is capped at the house's net load (load minus solar) and valued at full price (spot + grid + tax). Sweden has no net metering: power the house can't use can't be credited (owner decision, Nov 2026).
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
- `effekt_savings()` in economics.py: compares monthly peak demand WITH vs WITHOUT the investment. Not clamped: a higher peak is a cost. `solar_in_baseline=True` for existing panels
- `simulate()` is peak-aware under an EffektTariff: grid charging in measured hours is capped per month at the N-th highest no-battery daily peak (load − solar, × kw_factor), so charging never raises the top-N average. Hours with 0 kr/kW (Göteborg summer) are not capped
- Each operator has different measurement rules (top-N peaks from different days, peak hours, night discount)
- **Seasonal rates**: `low_season_rate` field for operators with different summer/winter effekt rates (e.g. SEOM: 72.5 kr/kW Apr-Oct, 145 kr/kW Nov-Mar). `get_effekt_rate(month)` returns correct rate.
- Battery peak shaving: discharge during high-load hours to reduce measured peak
- Simulated peak shaving is small: the scheduler only discharges for price arbitrage (no dedicated peak-shaving strategy). Default house, 32 kWh battery only: SEOM ~120 kr/yr, Ellevio ~0, Mälarenergi ~20, Göteborg ~90. With 15 kWp solar in the investment most of it is solar's own peak reduction (SEOM ~950, of which ~600 is the battery). The old "400-900 kr/mån" claim came from an accounting that dropped months where charging raised the peak

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
- Main optimization sweeps fuse sizes (user's selection + up to 3 larger) in outer loop
- Minimum fuse floor: must handle household peak load (house peak hour from the active load model + all scheduled loads running simultaneously). Hourly averages only: short peaks (stove, sauna) are not modelled
- Each battery label keeps only the fuse size with highest `profit_life` (net of fuse cost delta)
- `net_benefit_yr` = YEAR-1 benefit: battery part + counted solar part (with year-1 wear) − extra fuse subscription cost (vs user's selected fuse) − standby cost. The fuse comparison table shows year-1 amounts
- Recommends upgrades only. A smaller fuse the modelled load fits within is shown as a separate tip (`fuse_downgrade_tip`) and is never counted in the result: its fee saving needs no investment, and hourly averages hide short peaks
- Fuse comparison section shows pre-computed variants for recommended battery (no re-simulation)
- Fuse dropdown shows yearly fee per size (e.g. "20A — 1 780 kr/år")
- SEOM 2026 fuse fees: 16-25A=1,780 kr/yr (same tier), 35A=3,175, 50A=4,475, 63A=5,445

## Key design decisions
- **Recommendation-first**: app tells you what to buy, not the other way around
- **All battery sizes simulated**: editable price table with NKON defaults, user can add/remove
- **All tariffs tested**: per battery size, across operator's available tariff types. The saving is measured against staying on the operator's cheapest tariff without investing; a dearer tariff's extra bill (all household consumption) is a yearly cost in `fixed_part` (`tariff_switch_cost_yr`, detail line "varav tariffbyte"). Single-tariff operators are unaffected
- **Personal figures are examples** (owner decision, Nov 2026, "middle path"): technical defaults stay; battery prices, installation, solar size/price and the example house keep a value so the app works on a first visit, but the result is labelled "Exempelkalkyl" listing the untouched ones (`untouched_examples` on the `sim_inputs` snapshot; defaults live only in `example_inputs.py`). Operator, fuse and phases are never judged by value, only stated in the assumptions. No EV and no pool by default
- **Cashflow is "money in/out"**, not "profit" — language matters for user understanding
- **Monthly view** preferred over daily (bills are monthly)
- **Mortgage perspective**: financing section compares over battery LIFETIME, not loan term (50yr mortgage outlives 15yr battery)
- **Battery alone is profitable**: 32 kWh without solar saves ~4,800 kr/yr on Tidstariff arbitrage alone
- **Solar self-consumption value** only counted when solar is part of investment
- **The battery doesn't save kWh** — it shifts WHEN you buy (cheap night → expensive peak)
- **EV is smart-scheduled** (when added): wide availability window (18-07), picks cheapest hours day-ahead. Avoids effekttariff peak hours and tidstariff peak rates automatically. Poolvärmepump + varmvatten are flexibla laster (solar surplus)
- **Zero-export strategy**: default mode. Varmvatten element (3 kW, default 10 kWh/day) + luft-luft (pre-heat/cool) absorb surplus after battery. Solar surplus curtailed if no flex loads available. No export-capable inverter or microproducer registration needed. Export mode available as option with comparison showing it's typically worse than self-consumption.
- **Export comparison**: expandable section in results shows zero-export vs export side by side, with tipping point analysis. Conclusion: export only viable with effekttariff operators (SEOM) and consistently high daily spreads (>60 öre).
- **Session persistence**: opt-in via `ENERGIKALKYL_PERSIST=1` (`.app_state/session.json`); never on Streamlit Cloud
- **Tibber token**: kept in session state and passed as `token=`; never `os.environ`. Server-side token fallback only on self-hosted installs
- **Luft-luft is optional and separate**: shown outside main investment ROI, contribution reported as bonus
- **Tibber auto-fill**: one click fetches address, city, grid operator, fuse size, house area, residents, heating type, price area — all auto-configured
- **Tibber Insights calibration**: manual input of annual breakdown (heating/EV/active/always-on) for per-house h_loss fitting
- **Calibrated h_loss overrides energy class**: if consumption data is loaded, calibration runs BEFORE widget renders
- **No built-in optimism** (owner rule, Nov 2026): only neutral assumptions, shown to the user as assumptions (assumptions block under the recommendation, PDF methodology)
- **Wear and standby in every headline number**: benefit split into `bat_part` (arb_yr incl. effekt/export-baseline; falls linearly by the fade %/yr), `solar_part` (counted solar direct use; `SolarConfig.degradation_per_year` 0.5 %/yr, geometric) and `fixed_part` (−fuse fee delta − standby cost). Wear is evaluated mid-year (year − 0.5). `profit_life` = `lifetime_benefit` − battery investment − pro-rata solar investment; `payback` = `payback_years` (cumulative worn benefit, None if not within 25 yr); the annualized chart uses `benefit_life / lifetime`. Standby cost = W × 8.76 kWh × unweighted mean `total_cost_ore` of the chosen result
- **Five future scenarios** (0.7x, 1.0x, 1.5x, 2.5x, 4x): assumptions, not forecasts; no "likely"/analyst claims. Volatility ramps linearly to the target over 10 years; `vol_arb` holds the battery part per level, solar/fixed parts and wear are the same as the main result, so 1.0x equals `profit_life` exactly
- **Green deduction off by default**: the default prices are the owner's DIY figures (imported battery, self-mounted panels), which get no deduction. The option remains for buyers of an installed system
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
The app adds 25% Swedish VAT to these (`BATTERY_VAT` in app.py), so default table prices are incl. VAT.
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
- **Zero-export discharge IS capped at net load** (owner decision, Nov 2026). This makes very large batteries less profitable when the load profile is only a flat base load: realistic load data (Tibber/Vattenfall/heating model) matters for big sizes
- **Export split is separate from zero-export** — zero-export values all discharge as self-consumption. Export mode splits into self-consumption + export at different prices. Mixing the two broke profitability
- **Phase imbalance matters for fuse sizing** — 70% derating for 3-phase. 3× Victron MultiPlus-II with per-phase compensation is the only 48V option that eliminates this
- **Solar direct use = min(solar, load) per hour at that hour's price** (`solar_direct_use`). The old "production − battery − flex − export" counted curtailed solar as used, at the all-hours average price (9-15k kr/yr reported vs 6.7k true)
- **Effekt savings must not be clamped at 0, and charging must respect the peak** — the clamp hid up to −5,500 kr/yr (SEOM, 32 kWh) of extra demand charge caused by midday grid charging
- **Loan financing over battery lifetime = profit_life − interest paid in that period** (`loan_schedule`). Counting only loan payments ignored the ~84% of a 50-year loan still owed when the battery is worn out
- **Existing panels + export: subtract the no-battery export revenue** (`baseline_export_revenue`), and smart loads run exactly `daily_kwh` (last chosen hour at partial power; the EV was simulated as 33 kWh/day instead of 30)
- **One accounting everywhere**: the cumulative cashflow chart assumed 1 %/yr wear while every other number assumed a battery like new for its whole life and no standby draw. All headline numbers, charts, scenarios and the export comparison now use the same `yearly_benefit`/`lifetime_benefit`
- **Defaults must not hide losses**: a 99 kWh/day hot-water dump load swallowed ~48 kWh of surplus solar a day and hid curtailment; now 10 kWh/day and the detail view shows curtailed solar
- **Pick the tariff on the whole bill, not battery value alone**: with 1 phase the app switched to Enkeltariff for a slightly higher battery value although the household's bill without investing is ~2,100 kr/yr higher there (default house, 43,090 vs 45,232 kr/yr). Now `baseline_bill` per tariff, reference = cheapest, switch cost subtracted in `fixed_part`
- **A default EV was simulated for every visitor**: 30 kWh/day of EV charging (≈11,000 kWh/yr) for households without an EV inflated load and fuse floor. Now no scheduled loads by default (quick-add button instead)
- **Calibration must not edit a widget-backed value after the widget rendered**: the Tibber Insights calibration set the EV's kWh/day in the loads dict, but its number box (key `lk_i`) kept 30 and the loads were already built for that run, so the EV was simulated at the template's 30 kWh/day while the caption said 23.3 (found via the simulator's calculator validation). Now the value is queued (`_ev_cal_pending`) + `st.rerun()` and set before the widgets render; each EV load remembers the `cal_ev` it got so a later manual edit is kept
- **Cache what only depends on the month/year**: the cos³ solar curve (`solar._production_factors`, per month) was recomputed for every simulated hour — ~70 % of a simulation (1.7 s → 0.45 s); the holiday calendar (`tariff._swedish_holidays`, per year, frozenset) likewise
- **simulate() computes each slot's values once per day**: hour, month, prices, solar and house load used to be recomputed in each of the four passes (cost table, charge room, discharge tranches, execution); the charge→discharge pair loop hoists its lookups (same pairs, same order: the stable sort keeps ties). `to_hourly` returns a `HourlyPrices` list that later calls pass through; app.py converts the prices once. Verified identical slot by slot against the previous version on six setups (effekt tariffs, export, EV, flex, 16-25 A); app run 34 s → 23 s locally
- **A failed price download must not silently drop a day**: on a cold start (after a reboot) the app fetches ~1,100 days 20 at a time; a failed day was only printed to the server log and the calculation ran without it (example house 15,970 instead of 15,962 kr/yr). `fetch_range` now retries failed days twice (few at a time, after a pause, only when ≤ 5 % / 10 days failed) and returns the still-missing ones via `missing=`; the app warns (`price_days_missing`). Pressing Fetch again only fetches the missing days (disk cache)
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
- ~~No degradation modeling for battery capacity over time~~ — RESOLVED: linear capacity fade (input, default 1 %/yr) applied to the battery value, panel degradation 0.5 %/yr, standby power (input, default 45 W). The scheduler itself still simulates a new battery (full capacity every year); wear is applied to the value afterwards
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
