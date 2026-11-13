# Controller check: the NORVI controller itself

energikalkyl's result assumes a battery that does exactly what the day-ahead
plan says. The results page has a check, "Klarar ett riktigt styrsystem det
här?", that runs the NORVI energy controller (ESP32, Deye inverter, go-e
charger) through the recommended battery's period instead — the firmware's
own `controller.cpp`, minute by minute, in a simulated house, inverter,
charger and meter. See `controller_check.py`.

## What is here

| Path | From | What |
|---|---|---|
| `firmware/src`, `firmware/include` | norvi-energy-controller | the controller and everything it runs (planner, pipeline, fuse guard, house model, plant.h); unchanged |
| `sim/runner.cpp`, `sim/world.*`, `sim/controller_hal.cpp`, `sim/hal_stubs.cpp`, glue | energy-scheduler-sim (`wasm/`) | the period runner (moves the clock, feeds the days, adds up the money) and the simulated devices; no control rule |
| `sim/reference.cpp` | energy-scheduler-sim | the firmware planner on the calculator's own inputs (parity, ≤ 6-point program) |
| `check_main.cpp` | energikalkyl | reads the calculator's hourly values on stdin, sets the installation, runs, prints JSON |
| `VERSION` | `sync.sh` | the firmware and simulator commits the copy comes from |

`config.h` contains only placeholder network settings (no tokens or keys);
its constants (6 program points, 3 kW house reserve, GOE_MIN_AMPS) are what
the check uses; battery, fuse, EV energy, solar kWp and grid fees are set per
run through the firmware's `plant()`.

## How it runs

`controller_check.build_binary()` compiles the sources with g++ once per
source hash into `.controller_build/` (about 5 s). The check runs as a
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
