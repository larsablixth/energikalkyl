#pragma once
// ── The installation the controller runs (run-time, defaults = config.h) ───
//
// The sizes of the system — battery, inverter, fuse, house reserve, EV, solar
// panels, grid fees — used to be compile-time constants only. They are values
// here, read through plant(), so that
//   - the NORVI can take them from /settings.txt (settings.h) without a rebuild,
//   - the simulator and energikalkyl can run the same controller for other
//     battery / fuse / EV sizes and another grid tariff.
// The defaults are exactly the config.h values: with nothing changed the
// firmware behaves as before.
//
// Set it once before the controller starts (setup() / a simulation run);
// the controller only reads it.

#include "config.h"

struct Plant {
    // Battery + inverter
    float battery_capacity_kwh = BATTERY_CAPACITY_KWH;
    float inverter_max_bat_kw  = INVERTER_MAX_BAT_KW;   // battery charge/discharge via the inverter
    float battery_charge_kw    = BATTERY_CHARGE_KW;     // battery hardware limit
    float battery_efficiency   = BATTERY_EFFICIENCY;    // round trip
    int   battery_min_soc      = BATTERY_MIN_SOC;       // %
    int   battery_max_soc      = BATTERY_MAX_SOC;       // %
    // Main fuse + house
    int   fuse_nominal_amps    = FUSE_NOMINAL_AMPS;
    float fuse_phase_derating  = FUSE_PHASE_DERATING;
    float base_load_kw         = BASE_LOAD_KW;          // house reserve on the fuse
    // EV
    float ev_daily_kwh         = EV_DAILY_KWH;
    int   ev_window_start_h    = EV_WINDOW_START_H;
    int   ev_window_end_h      = EV_WINDOW_END_H;
    int   ev_priority_mode     = static_cast<int>(EV_PRIORITY_MODE);
    // Solar (default PV forecast model)
    float solar_kwp            = SOLAR_KWP;
    // Planner
    float min_spread_sek       = MIN_SPREAD_SEK;
    // Grid transfer fee incl. energy tax (SEK/kWh): high-load / other time.
    // A flat (single-rate) tariff = the same value in both.
    float grid_fee_high_sek    = GRID_FEE_HIGH;
    float grid_fee_low_sek     = GRID_FEE_LOW;
};

/** The installation in force (read-only for the controller). */
const Plant& plant();
/** To set it before the controller starts. */
Plant* plant_mutable();
