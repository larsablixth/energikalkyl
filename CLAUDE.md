# CLAUDE.md

## Project: Energikalkyl — El, Sol & Batteri

Swedish electricity price analysis tool. Simulates home battery + solar profitability based on historical spot prices, real consumption data, grid tariffs, and investment costs.

## How to run
```bash
streamlit run app.py                    # Web GUI on port 8501
python elpriser.py batteri --help       # CLI help
```

## Key files
- `app.py` — Streamlit web GUI (main user interface)
- `batteri.py` — Battery simulation engine (BatteryConfig, LoadSchedule, FlexibleLoad, simulate)
- `elpriser.py` — CLI, price fetching from elprisetjustnu.se (cached in .price_cache/)
- `solar.py` — Solar production model (Stockholm, cos³ curve, configurable kWp)
- `tariff.py` — Vattenfall Tidstariff/Enkeltariff 2026 rates and fuse fees
- `tibber_source.py` — Tibber GraphQL API (prices, consumption, seasonal profiles)
- `entsoe_source.py` — ENTSO-E API + EUR/SEK via ECB (frankfurter.app)
- `import_vattenfall.py` — Parse Vattenfall Eldistribution Excel (Serie sheet, column 6 = Summa/dag)
- `import_consumption.py` — Generic CSV consumption import

## Critical implementation details

### Simulation strategy (batteri.py simulate())
- Multi-cycle: up to 3 charge/discharge cycles per day when spread justifies it
- Minimum 20 öre/kWh absolute spread required to cycle (avoid wear on low-spread days)
- Solar-aware: estimates expected daily solar surplus and reduces grid charging to leave room for free solar
- Priority chain: household load → flex loads (pool) → battery charging → grid export
- Charging power limited by fuse headroom (fuse capacity - household load at that hour)
- Both tariffs (Tidstariff + Enkeltariff) simulated automatically — best picked as result

### Solar model (solar.py)
- cos³ curve for realistic peak concentration (15 kWp peaks at ~8 kW in June, not nameplate)
- Monthly kWh/kWp values for Stockholm south-facing 35° tilt
- Daylight hours vary by month (3.5h-21.5h in June, 9h-15h in December)

### Vattenfall Excel import (import_vattenfall.py)
- Actual data is in "Serie" sheet column 6 (Summa/dag) — daily totals
- Tim-sheets have cross-sheet formulas openpyxl can't evaluate
- openpyxl with data_only=True required

### EUR/SEK conversion (entsoe_source.py)
- Uses ECB rate from day BEFORE delivery (Nord Pool convention)
- Cached in .fx_cache.json

### Tariffs (tariff.py)
- Peak hours (höglasttid): Jan-Mar + Nov-Dec, weekdays 06-22, excluding Swedish public holidays
- Easter calculated with Anonymous Gregorian algorithm
- Tidstariff 2026: peak 76.5, off-peak 30.5 öre/kWh
- Enkeltariff 2026: 44.5 öre/kWh all hours
- Energy tax: 54.88 öre/kWh (43.90 + 25% moms)
- Same abonnemangsavgift for both tariffs per fuse size

### Fuse fees (Vattenfall 2026, kr/år)
16A: 5775, 20A: 8085, 25A: 10125, 35A: 13890, 50A: 19945, 63A: 26875

## User's setup (reference)
- Location: Sigtuna/Stockholm (SE3)
- Grid: Vattenfall Eldistribution, 25A 3-phase
- Electricity provider: Tibber
- Solar: 15 kWp south-facing (panels ~800 kr each, glas-glas)
- EV: 11 kW charger, charges at night 23-06 (car at work during day)
- Pool: heat pump 3 kW, May-Sep, ~20 kWh/day
- Considering: NKON ESS Pro 32.15 kWh battery (+ possibly 16 kWh extra)
- Consumption: ~20,000 kWh/year (from Vattenfall Excel, 4 files 2023-2026)
- Vattenfall data files: /mnt/c/Users/user/Downloads/2000304738_*.xlsx

## NKON ESS Pro prices (EUR excl. VAT, ~Q1 2025)
- 5.12 kWh: €600, 10.24 kWh: €1177, 16.1 kWh: €1512, 32.15 kWh: €2857
- Max charge/discharge: 15 kW (32 kWh), 11 kW (16 kWh)
- LiFePO4, 8000 cycles, Seplos 300A BMS
- Supports parallel connection (up to 16 units)

## Key design decisions
- Cashflow is "money in/out", not "profit" — language matters
- Both tariffs simulated automatically — user doesn't choose
- Monthly view preferred over daily (bills are monthly)
- Typical year (Jan-Dec) instead of historical dates
- Battery optimizer uses NKON list prices, main results use user's input
- Solar self-consumption value only counted when solar is part of investment
- The battery doesn't save kWh — it shifts WHEN you buy (cheap night → expensive peak)
- EV is fixed night load (car at work during day), pool is flex daytime load

## API keys (not in repo)
- `.entsoe_key` — ENTSO-E transparency platform token
- `.tibber_token` — Tibber personal access token

## Known issues / future work
- Solar model is simplified (monthly averages, no weather variation)
- No degradation modeling for battery capacity over time
- Tibber hourly data limited to ~30 days, monthly goes back ~12 months
- Pool heat pump modeled as constant 3 kW but real heat pumps vary with temperature
- EV daily consumption assumed constant but varies seasonally
