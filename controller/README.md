# Controller check: the NORVI controller's planning code

energikalkyl's result assumes a battery that does exactly what the day-ahead
plan says. The results page has a check, "Klarar ett riktigt styrsystem det
här?", that runs the recommended battery's hours through a real controller's
planner instead: the NORVI energy controller firmware (ESP32, Deye inverter,
go-e charger). See `controller_check.py`.

## What is here

| Path | From | What |
|---|---|---|
| `firmware/src`, `firmware/include` | norvi-energy-controller | the planner (`battery_plan`), tariff/scheduler, fuse budget, Deye program builder, local time; unchanged |
| `sim/batch.cpp` + glue | energy-scheduler-sim (`wasm/`) | `bt_plan_day()`: firmware planning per day with run-time battery, fuse and EV settings, and the reference chains |
| `check_main.cpp` | energikalkyl | reads the calculator's hourly values on stdin, prints the summed chains as JSON |
| `VERSION` | `sync.sh` | the firmware and simulator commits the copy comes from |

`config.h` contains only placeholder network settings (no tokens or keys);
its planning constants (6 program points, 3 kW house reserve, EV window,
GOE_MIN_AMPS) are what the check uses.

## How it runs

`controller_check.build_binary()` compiles the sources with g++ once per
source hash into `.controller_build/` (about 2 s). The check runs as a
separate process because the firmware sets the process time zone to
Europe/Stockholm. Streamlit Cloud installs g++ from `packages.txt`; the
Docker image compiles it at build time. Without a compiler the app shows
that the check is not available.

## Updating from the firmware

```bash
bash controller/sync.sh ../norvi-energy-controller ../energy-scheduler-sim
python3 -m pytest -q -k "Controller or EnergyFlows"
```

The parity test (`TestControllerCheck`) fails if the firmware planner no
longer reproduces the calculator on its own inputs.
