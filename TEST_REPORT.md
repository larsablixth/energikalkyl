# Energikalkyl - Test Report

**Date:** 2026-03-27
**Version:** Current main branch
**Tested by:** Automated test suite (pytest)
**Result: ALL 69 TESTS PASSED**

---

## What is this report?

This report summarizes the quality checks performed on the Energikalkyl application — a tool that helps homeowners decide whether to invest in home batteries and/or solar panels. The tests verify that the calculations and logic the app relies on are correct.

---

## Summary

| Area tested | Tests | Result |
|---|---|---|
| Electricity pricing (tariffs) | 25 | All passed |
| Heating model | 10 | All passed |
| Solar panel production | 9 | All passed |
| Battery simulation | 23 | All passed |
| End-to-end (full system) | 2 | All passed |
| **Total** | **69** | **All passed** |

### Code quality check

| Check | Files | Result |
|---|---|---|
| Code syntax valid | 18 of 18 | All OK |
| Modules load correctly | 17 of 18 | 17 OK, 1 environment-specific issue (PDF report, not a code bug) |

---

## What was tested — in plain language

### 1. Electricity pricing (25 tests)

These tests verify that the app correctly calculates what you pay for electricity depending on your grid operator, time of day, and season.

| What we checked | Why it matters | Result |
|---|---|---|
| Peak hours detected correctly (winter weekdays 06-22) | You pay more during peak hours — wrong detection = wrong savings estimate | Passed |
| Swedish holidays treated as off-peak | Holidays like Christmas and Easter have lower rates | Passed |
| Summer months are always off-peak | No peak pricing April-October | Passed |
| Weekends are always off-peak | Saturday/Sunday have lower rates | Passed |
| Easter dates calculated correctly (2025 and 2026) | Easter moves every year — must be computed | Passed |
| Time-of-use tariff (Tidstariff) calculates correct costs | Peak: 76.5 + 45.0 ore/kWh, Off-peak: 30.5 + 45.0 ore/kWh | Passed |
| Flat tariff (Enkeltariff) charges same rate all hours | 44.5 + 45.0 ore/kWh regardless of time | Passed |
| Power demand tariff (Effekttariff) calculates correctly | Energy cost + demand charge based on peak usage | Passed |
| Night discount applied correctly (50% for Ellevio) | Lower demand charge at night reduces your bill | Passed |
| Seasonal rates work (SEOM: 145 kr/kW winter, 72.5 summer) | Different charge rates by season | Passed |
| All 8 grid operators have correct settings | Vattenfall, Ellevio, E.ON, Goteborg Energi, Malarenergi, Jamtkraft, SEOM, Custom | Passed |
| Fuse fees match 2026 rates | Your subscription cost depends on fuse size | Passed |
| Tariff objects created correctly for each operator | The app builds the right pricing model for your operator | Passed |

### 2. Heating model (10 tests)

These tests verify that the app correctly estimates how much electricity your house uses for heating, based on outdoor temperature and your heating system.

| What we checked | Why it matters | Result |
|---|---|---|
| Heat demand increases as temperature drops | Colder outside = more heating needed | Passed |
| No heating needed above 21 degrees C | Above indoor setpoint, heating turns off | Passed |
| Ground-source heat pump efficiency (COP) calculated correctly | COP determines how much electricity the heat pump uses per kW of heat | Passed |
| COP never drops below minimum (1.0) | Even in extreme cold, COP stays realistic | Passed |
| Zero electricity use on warm days | No heating = no heating electricity | Passed |
| Heating electricity increases on cold days | -10 degrees C requires significant power | Passed |
| Backup electric heater (elpatron) activates when needed | When the heat pump can't keep up, the backup heater kicks in | Passed |
| Air-to-air heat pump supplement reduces primary system load | Adding a luft-luft VP saves electricity | Passed |
| Cooling only activates above threshold (24 degrees C) | AC doesn't run unnecessarily | Passed |
| No cooling without air-to-air system enabled | If you don't have AC, no cooling cost | Passed |

### 3. Solar panel production (9 tests)

These tests verify that the app correctly estimates how much electricity your solar panels produce throughout the year.

| What we checked | Why it matters | Result |
|---|---|---|
| Hourly production factors add up to 100% per day | All solar energy is accounted for across the day | Passed |
| Zero production at midnight (all months) | Solar panels don't produce in the dark | Passed |
| Peak production at midday | Noon should always be the highest production hour | Passed |
| Summer produces much more than winter | June produces 3x+ more than December in Stockholm | Passed |
| Yearly estimate is realistic (10 kWp = 7,000-12,000 kWh) | Total production matches real-world Swedish data | Passed |
| Lifetime production accounts for panel degradation (0.5%/year) | Panels slowly lose efficiency over 25 years | Passed |
| Real measured data overrides the model when available | If you have actual inverter data, the app uses that instead of estimates | Passed |
| Model used as fallback when no real data exists | Without real data, the built-in model provides reasonable estimates | Passed |
| Monthly scaling adjusts model to match real totals | Combines real monthly totals with model hourly shape for best accuracy | Passed |

### 4. Battery simulation (23 tests)

These tests verify the core engine that simulates how a home battery charges and discharges to save you money.

| What we checked | Why it matters | Result |
|---|---|---|
| EV charging window works (e.g., 18:00-07:00) | Your car charges during the hours you set | Passed |
| Overnight window wraps past midnight correctly | 18:00-07:00 includes both evening and early morning | Passed |
| Smart EV charging picks cheapest hours | Instead of charging all night, picks the 3 cheapest hours | Passed |
| Pool heat pump only runs in summer | Seasonal loads don't waste energy in winter | Passed |
| Hot water element available year-round | Always-on flexible loads work every month | Passed |
| Fuse capacity calculated correctly (3-phase with derating) | 25A x 230V x 3 phases x 70% = 12.1 kW usable | Passed |
| Fuse capacity correct for single-phase | No derating needed for 1-phase installations | Passed |
| Usable battery capacity respects min/max charge limits | 32 kWh battery with 5-95% limits = 28.8 kWh usable | Passed |
| Household load adds scheduled loads correctly | Base load + EV = total load at that hour | Passed |
| Charging limited by fuse headroom | Can't charge battery if the fuse is already near its limit | Passed |
| Temperature-based load profiles work | Heating load varies by hour and date based on weather | Passed |
| Battery charges when cheap, discharges when expensive | The core money-saving strategy works correctly | Passed |
| Battery makes profit with price spread | With realistic price differences, the battery saves money | Passed |
| Battery doesn't cycle with flat prices | No point charging/discharging when all hours cost the same | Passed |
| Simulation works with all three tariff types | Tidstariff, Enkeltariff, and Effekttariff all simulate correctly | Passed |
| Simulation works with solar panels | Battery + solar panels simulate together correctly | Passed |
| Simulation works without any tariff (spot price only) | Fallback mode works for users without grid tariff data | Passed |
| Smart EV + battery simulate together | Complex scenario with smart-scheduled EV and battery arbitrage | Passed |

### 5. End-to-end integration (2 tests)

| What we checked | Why it matters | Result |
|---|---|---|
| Fuse fees match between battery config and tariff module | Both parts of the system agree on subscription costs | Passed |
| Solar production feeds into battery simulation | The full chain (solar panels -> battery -> savings) works together | Passed |

---

## What is NOT yet tested

- PDF report generation (environment dependency issue)
- Tibber API data fetching (requires API key)
- PVGIS satellite data fetching (requires network)
- Vattenfall Excel import (requires sample files)
- The web interface (Streamlit app.py)
- Weather data from SMHI

These areas rely on external services and would require separate integration testing with real API keys and data files.

---

## How to run the tests yourself

```bash
python -m pytest test_energikalkyl.py -v
```

Expected output: `69 passed` in under 1 second.

---

## Conclusion

The core calculation engine is working correctly. All pricing, heating, solar, and battery simulation logic produces expected results. The app can be trusted to give accurate investment recommendations based on the data it receives.
