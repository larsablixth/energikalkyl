#pragma once
// Force-included (-include wasm/sim_overrides.h) into every translation unit
// of the simulator build, firmware sources included.
//
// RULE: nothing in this file may change anything the firmware computes —
// no config.h constant, no tariff, no fuse limit, no planner parameter.
// config.h is used exactly as committed in the firmware (firmware/include).
// Runtime differences (battery size, fuse, tariff of the calculator being
// validated) are passed as PlanParams / buy costs through the documented
// firmware APIs in wasm/batch.cpp, never by redefining constants.
//
// Build glue only:
#define ENERGY_SCHEDULER_SIM 1
