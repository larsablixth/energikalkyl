// ── Reference results for "Validate calculator" ───────────────────────────
//
// The firmware PLANNER (battery_plan.h), not the controller, on the
// calculator's own hourly inputs — to show where the calculator and the real
// controller part ways:
//   ideal     bat_plan_day + bat_execute_plan: the firmware planner on the
//             calculator's inputs (load incl. EV, perfect data, discharge on
//             command) — must equal energikalkyl ("parity")
//   progperf  the same plan as a Deye program (bat_plan_program, ≤ 6 points)
//             run by the firmware's Deye model (bat_simulate_program)
// Everything after that — EV + fuse budget, forecast, look-ahead, learning,
// fuse guard, execution — is the real controller in the simulated world
// (wasm/runner.cpp), not a model of it. These are firmware functions called
// on given data: no planning or control rule lives here.

#include <emscripten/emscripten.h>
#include <algorithm>
#include <cstring>

#include "config.h"
#include "plant.h"
#include "battery_plan.h"
#include "tou_window.h"

namespace {

constexpr int N = PLAN_MAX_SLOTS;
enum { R_BUY = 0, R_LOAD, R_SOLAR, R_ROWS };
float s_in[R_ROWS * N];
float s_out[16];

struct Params {
    float capacity_kwh = 64.0f, max_charge_kw = 12.5f, max_discharge_kw = 12.5f;
    float efficiency = 0.9f, min_soc = 0.15f, max_soc = 0.95f, min_spread = 0.20f;
    float grid_max_kw = 12.075f;
    int segments = MAX_PROG_SEGMENTS;
} s_p;

void put(int at, const DayMoney& m) {
    s_out[at + 0] = m.net();
    s_out[at + 1] = m.charge_cost;
    s_out[at + 2] = m.discharge_value;
    s_out[at + 3] = m.charged_kwh;
    s_out[at + 4] = m.discharged_kwh;
    s_out[at + 5] = m.end_level;
}

}  // namespace

extern "C" {

EMSCRIPTEN_KEEPALIVE float* ref_in_ptr() { return s_in; }
EMSCRIPTEN_KEEPALIVE int ref_in_stride() { return N; }
EMSCRIPTEN_KEEPALIVE float* ref_out_ptr() { return s_out; }

// Battery (energikalkyl units: kWh, kW, %, SEK) and the calculator's grid
// limit (fuse A × phases × V × phase balance / 1000).
EMSCRIPTEN_KEEPALIVE
void ref_set_battery(float capacity_kwh, float max_charge_kw, float max_discharge_kw, float efficiency,
                     float min_soc_pct, float max_soc_pct, float min_spread_sek, float grid_max_kw) {
    s_p.capacity_kwh = capacity_kwh;
    s_p.max_charge_kw = max_charge_kw;
    s_p.max_discharge_kw = max_discharge_kw;
    s_p.efficiency = efficiency;
    s_p.min_soc = min_soc_pct / 100.0f;
    s_p.max_soc = max_soc_pct / 100.0f;
    s_p.min_spread = min_spread_sek;
    s_p.grid_max_kw = grid_max_kw;
}

// One day: rows R_BUY (SEK/kWh), R_LOAD (kWh per slot incl. EV), R_SOLAR.
// Levels = stored kWh above the floor carried from the previous day.
// Out: [0..5] ideal, [6..11] progperf (net, charge_cost, discharge_value,
// in, out, end_level).
EMSCRIPTEN_KEEPALIVE
void ref_plan_day(int n, int slot_min, float lvl_ideal, float lvl_progperf) {
    std::memset(s_out, 0, sizeof(s_out));
    if (n <= 0 || n > N || slot_min <= 0) return;
    const float slot_h = slot_min / 60.0f;
    PlanParams pp;
    pp.slot_h = slot_h;
    pp.capacity_kwh = s_p.capacity_kwh;
    pp.min_soc = s_p.min_soc;
    pp.max_soc = s_p.max_soc;
    pp.efficiency = s_p.efficiency;
    pp.max_charge_kw = s_p.max_charge_kw;
    pp.max_discharge_kw = s_p.max_discharge_kw;
    pp.min_spread = s_p.min_spread;
    pp.export_enabled = false;
    static PlanSlot act[N];
    for (int i = 0; i < n; i++) {
        PlanSlot x;
        x.buy_cost = s_in[R_BUY * N + i];
        x.export_value = 0.0f;
        x.load_kwh = s_in[R_LOAD * N + i];
        x.solar_kwh = s_in[R_SOLAR * N + i];
        x.grid_room_kwh = std::max(0.0f, std::min(s_p.max_charge_kw, s_p.grid_max_kw - x.load_kwh / slot_h)) * slot_h;
        act[i] = x;
    }
    static BatteryPlan plan_i, plan_p;
    bat_plan_day(act, n, 0, pp, lvl_ideal, &plan_i);
    put(0, bat_execute_plan(&plan_i, act, n, pp, lvl_ideal));
    static PlanSegment segs[N];
    bat_plan_day(act, n, 0, pp, lvl_progperf, &plan_p);
    const int ns = bat_plan_program(&plan_p, act, 0, pp, s_p.segments, segs);
    put(6, bat_simulate_program(segs, ns, act, n, 0, pp, lvl_progperf));
}

}  // extern "C"
