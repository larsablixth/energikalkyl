#pragma once
// ── Simulated world in C++ (for whole-period runs) ─────────────────────────
//
// The same physics as sim-hardware.js (DeyeSim, GoeSim, GridMeter), used by
// wasm/runner.cpp to run the NORVI's controller over months or years quickly
// (year batch, "Validate calculator", energikalkyl's controller check). The
// world is physics only: it executes what the controller wrote (the Deye's
// 6-point program, the go-e current) — it makes no decision.

#include <cstdint>

struct DeyeWorld {
    // configuration
    float capacity_kwh = 64.0f;
    float min_soc = 15.0f, max_soc = 95.0f;         // %
    float max_charge_kw = 12.5f, max_discharge_kw = 12.5f;
    float efficiency = 0.90f;                       // round trip
    bool  realistic = false;                        // "realistic" loss model (√η, standby, taper)
    bool  export_enabled = false;
    float v_charge_max = 57.6f, inverter_eff = 0.96f, standby_kw = 0.05f;
    // state
    float soc = 50.0f;
    struct Point { int start_min = -1; int power_w = 0; int soc = 0; bool grid = false; };
    Point points[6];
    int  n_points = 0;
    int  grid_charge_enable = 0, grid_charge_current_a = 0, tou_enable = 0;
    // flows of the last step (kW)
    float grid_charge_kw = 0, solar_charge_kw = 0, solar_direct_kw = 0, served_kw = 0;
    float export_kw = 0, curtailed_kw = 0, grid_draw_kw = 0, load_kw = 0, pv_kw = 0;

    void write_program(const uint16_t* regs);       // 27-value image (sim_hal.h)
    bool grid_charge_programmed() const;
    int  point_at(int minute) const;
    void tick(int minute, float dt_h, float load, float solar, bool grid_charge_allowed);
};

struct GoeWorld {
    bool  car_connected = false;
    int   amps = 0;
    int   min_amps = 6, max_amps = 16;
    float phases = 3, voltage = 230, obc_max_kw = 11.0f;
    float need_kwh = 0;            // energy the car still wants today
    float draw_kw = 0;

    void set_amps(int a);
    float tick(float dt_h);
};

struct MeterWorld {
    float shares[3] = {0.43f, 0.33f, 0.24f};
    float voltage = 230;
    float l1 = 0, l2 = 0, l3 = 0, power_w = 0;
    void update(float house_kw, float deye_grid_kw, float ev_kw, bool ev_behind_ct);
};
