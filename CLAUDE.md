# CLAUDE.md

## Project: Energikalkyl — El, Sol & Batteri

Swedish electricity price analysis and home battery/solar profitability simulator.

## Key files
- `elpriser.py` — CLI main, price fetching, all commands
- `app.py` — Streamlit web GUI
- `batteri.py` — Battery simulation engine (BatteryConfig, simulate, FlexibleLoad, fuse_analysis)
- `solar.py` — Solar production model for Stockholm
- `tariff.py` — Vattenfall Tidstariff/Enkeltariff 2026 rates and fuse fees
- `tibber_source.py` — Tibber GraphQL API integration
- `entsoe_source.py` — ENTSO-E API + EUR/SEK via ECB
- `import_vattenfall.py` — Parse Vattenfall Eldistribution Excel files (Serie sheet, column 6 = Summa/dag)
- `import_consumption.py` — Generic CSV consumption import

## Important implementation details
- Vattenfall Excel: actual data is in "Serie" sheet column 6 (Summa/dag), NOT in Tim-sheets (those have cross-sheet formulas openpyxl can't evaluate)
- EUR/SEK conversion uses ECB rate from day BEFORE delivery (Nord Pool convention)
- Price cache in `.price_cache/` — one JSON per day, concurrent fetching with 20 threads
- Tibber hourly data limited to ~30 days, but monthly data goes back ~12 months
- Peak hours (höglasttid): Jan-Mar + Nov-Dec, weekdays 06-22, excluding Swedish public holidays
- Fuse analysis warns about overload, no-charge, and limited-charge conditions

## Running
```bash
streamlit run app.py                    # Web GUI on port 8501
python elpriser.py batteri --help       # CLI help
```

## API keys (not in repo)
- `.entsoe_key` — ENTSO-E transparency platform token
- `.tibber_token` — Tibber personal access token
