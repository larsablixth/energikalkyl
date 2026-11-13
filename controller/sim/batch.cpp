// ── Batch day planning (year runs and calculator validation) ────────────
//
// The batch worker (batch-worker.js) runs many days quickly. Per day it calls
// bt_plan_day(), which plans with the FIRMWARE's planning functions and
// returns the Deye program register image for the simulated Deye (JS) to
// execute, the EV amps per slot, plus three reference results that split
// the gap between energikalkyl and the controller into causes:
//
//   ideal     bat_plan_day + bat_execute_plan on the calculator's own inputs
//             (load incl. EV, perfect data, discharge on command) — the
//             energikalkyl parity number (firmware README: "to the krona")
//   progperf  the ideal plan → ≤ N program segments (bat_plan_program) →
//             bat_simulate_program: cost of what a Deye program can express
//   ctrlperf  the controller's plan exactly as pipeline_plan() builds it
//             (house load forecast without the EV, EV planned with
//             ev_plan_day on the shared fuse budget; with DEYE_CT_SEES_GOE
//             plan_shared_day adds the planned EV to the load the battery
//             planner and the Deye model see), perfect forecast
//   ctrlmodel the same with the FORECAST the controller had (model, or
//             perfect) — the program the simulated Deye then executes
//
// plan_controller() mirrors pipeline_plan_mode() (firmware/src/pipeline.cpp:
// SharedDayInput → plan_shared_day, battery/EV order fixed or AUTO)
// step by step, but takes battery size, fuse budget, tariff and EV settings
// at run time (pipeline_plan reads them from config.h constants). The
// native driver (wasm/native/driver.cpp) asserts that with config.h values
// it produces the SAME program segments and EV amps as pipeline_prepare_day
// — that test is what keeps this mirror honest.
//
// Known firmware build limits that the batch reports instead of hiding:
//   - EXPORT_PRICE_FACTOR = 0 → battery export arbitrage is never planned
//     (MAX_TRANCHES is a compile-time constant in battery_plan.cpp)
//   - ev_plan_day converts kW ↔ amps with FUSE_PHASES / FUSE_VOLTAGE
//   - the batch plans with EV demand every day (pipeline_step's ev_absent
//     replan when no car is plugged in is not modelled)

#include <emscripten/emscripten.h>
#include <cstring>
#include <cmath>
#include <algorithm>

#include "config.h"
#include "tariff.h"
#include "fuse.h"
#include "scheduler.h"
#include "battery_plan.h"
#include "deye_program.h"
#include "time_local.h"
#include "sim_hal.h"

namespace {

constexpr int N = PLAN_MAX_SLOTS;

// Input rows (JS writes floats at bt_in_ptr() + row * N + slot)
enum InRow {
    IN_SPOT = 0,      // spot SEK/kWh excl. VAT
    IN_BUY,           // buying cost SEK/kWh (used when use_fw_tariff == 0)
    IN_HOUSE,         // actual house load behind the Deye, kWh/slot (no EV)
    IN_SOLAR,         // actual PV, kWh/slot
    IN_FC_HOUSE,      // forecast house load, kWh/slot
    IN_FC_SOLAR,      // forecast PV, kWh/slot
    IN_EV_CALC,       // EV kWh/slot inside the CALCULATOR's load (ideal only)
    IN_ROWS
};
float s_in[IN_ROWS * N];

struct Params {
    float capacity_kwh = BATTERY_CAPACITY_KWH;
    float max_charge_kw = INVERTER_MAX_BAT_KW;
    float max_discharge_kw = INVERTER_MAX_BAT_KW;
    float efficiency = BATTERY_EFFICIENCY;
    float min_soc = BATTERY_MIN_SOC / 100.0f;
    float max_soc = BATTERY_MAX_SOC / 100.0f;
    float min_spread = MIN_SPREAD_SEK;
    float grid_max_kw = FUSE_NOMINAL_AMPS * FUSE_PHASES * FUSE_VOLTAGE * FUSE_PHASE_DERATING / 1000.0f;
    float base_load_kw = BASE_LOAD_KW;
    int   segments = MAX_PROG_SEGMENTS;
    bool  use_fw_tariff = true;
    bool  export_enabled = false;
    float export_factor = 0.0f;
    float export_fee = EXPORT_FEE_SEK;
    bool  ev_enabled = true;
    int   ev_win_start = EV_WINDOW_START_H;
    int   ev_win_end = EV_WINDOW_END_H;
    float ev_daily_kwh = EV_DAILY_KWH;
    EvPriorityMode ev_mode = EV_PRIORITY_MODE;
};
Params s_p;

// Outputs
constexpr int OUT_MONEY = 6;   // net, charge_cost, discharge_value, in, out, end_level
float s_out[64];
int   s_seg[4 * MAX_PROG_SEGMENTS];   // start_min[6], grid[6], soc[6], power_w[6]
uint16_t s_regs[HAL_PROGRAM_REGS];
int   s_ev[N];
int   s_charge[N];
float s_buy[N];
float s_exp[N];

void put_money(int at, const DayMoney& m) {
    s_out[at + 0] = m.net();
    s_out[at + 1] = m.charge_cost;
    s_out[at + 2] = m.discharge_value;
    s_out[at + 3] = m.charged_kwh;
    s_out[at + 4] = m.discharged_kwh;
    s_out[at + 5] = m.end_level;
}

PlanParams plan_params(float slot_h) {
    PlanParams pp;
    pp.slot_h = slot_h;
    pp.capacity_kwh = s_p.capacity_kwh;
    pp.min_soc = s_p.min_soc;
    pp.max_soc = s_p.max_soc;
    pp.efficiency = s_p.efficiency;
    pp.max_charge_kw = s_p.max_charge_kw;
    pp.max_discharge_kw = s_p.max_discharge_kw;
    pp.min_spread = s_p.min_spread;
    pp.export_enabled = s_p.export_enabled;
    return pp;
}

struct CtrlPlan {
    SharedDayPlan sp;                 // plan_shared_day output (segments, ps, EV)
    const PlanSegment* segs = nullptr;
    int ns = 0;
    const PlanSlot* ps = nullptr;
    ProgSegment prog[MAX_PROG_SEGMENTS];
    int n_prog = 0;
    bool plan[N] = {};
    const uint8_t* ev_amps = nullptr;
    float ev_kwh = 0.0f;
    float value = 0.0f;
    float bat_charge_kw = 0.0f;
    float fuse_avail = 0.0f;
};

// Mirror of pipeline_plan_mode(ctx, soc, from_slot = 0, mode) with run-time
// params: same SharedDayInput, then plan_shared_day (firmware), then the
// same segment → program-point conversion.
void plan_controller(int n, int slot_min, const DaySlotClock& clk, const float* cost,
                     const int* start_min, const float* load_kwh, const float* solar_kwh,
                     float start_level, CtrlPlan* out) {
    const float slot_h = static_cast<float>(slot_min) / 60.0f;
    /* pipeline_prepare_day: fuse budget and battery grid-charge rate */
    const float fuse_avail = std::max(0.0f, s_p.grid_max_kw - s_p.base_load_kw);
    out->fuse_avail = fuse_avail;
    out->bat_charge_kw = std::min(fuse_avail, s_p.max_charge_kw);   // fuse_split_budget(.., false).bat_kw

    SharedDayInput in;
    in.n = n;
    in.group = 1;
    in.slot_h_price = slot_h;
    in.buy_cost = cost;
    in.export_value = s_exp;
    in.local_start_min = start_min;
    in.load_kwh = load_kwh;
    in.solar_kwh = solar_kwh;
    in.grid_max_kw = fuse_avail + s_p.base_load_kw;
    in.bat_charge_kw = out->bat_charge_kw;
    in.from_slot = 0;
    in.max_segments = s_p.segments;
    in.pp = plan_params(slot_h);
    in.start_level_kwh = start_level;
    in.ev_win_start_h = s_p.ev_win_start;
    in.ev_win_end_h = s_p.ev_win_end;
    in.ev_kwh = s_p.ev_enabled ? s_p.ev_daily_kwh : 0.0f;
    plan_shared_day(in, s_p.ev_mode, &out->sp);

    const SharedDayPlan& sp = out->sp;
    out->segs = sp.segs;
    out->ns = sp.n_segs;
    out->ps = sp.ps;
    out->ev_amps = sp.ev_amps;
    out->ev_kwh = sp.ev_kwh;
    out->value = sp.bat.net();

    /* segments → plan[] and program points (local minutes) */
    for (int i = 0; i < n; i++) {
        int k = 0;
        while (k + 1 < out->ns && out->segs[k + 1].start_slot <= i) k++;
        out->plan[i] = out->ns > 0 && out->segs[k].grid_charge;
    }
    out->n_prog = 0;
    for (int k = 0; k < out->ns && k < MAX_PROG_SEGMENTS; k++) {
        const int first = out->segs[k].start_slot;
        const int st = (k == 0) ? 0 : slot_local_start_min(&clk, first);
        if (out->n_prog > 0 && st <= out->prog[out->n_prog - 1].start_min) continue;
        ProgSegment p;
        p.start_min = st;
        p.grid_charge = out->segs[k].grid_charge;
        p.soc = out->segs[k].soc_pct;
        p.power_w = 0;
        if (p.grid_charge) {
            const float pw = std::min(out->bat_charge_kw,
                bat_segment_power_kw(out->segs, out->ns, k, sp.ps, sp.m, 0, slot_h));
            p.power_w = static_cast<int>(std::max(0.0f, pw) * 1000.0f);
        }
        out->prog[out->n_prog++] = p;
    }
}

CtrlPlan s_perf, s_fc;

}  // namespace

// Exposed for the native parity test (same translation unit not needed).
int batch_plan_controller_for_test(int y, int m, int d, int n, int slot_min, const float* spot,
                                   const float* fc_load, const float* fc_solar, float soc_pct,
                                   ProgSegment* prog_out, uint8_t* ev_out, float* value_out) {
    LocalDate ld; ld.year = y; ld.month = m; ld.day = d;
    const DaySlotClock clk = day_slot_clock_for(ld, slot_min, n);
    static float cost[N];
    static int st[N];
    scheduler_day_buy_costs(spot, n, slot_min, y, m, d, cost);
    for (int i = 0; i < n; i++) { st[i] = slot_local_start_min(&clk, i); s_exp[i] = tariff_export_value(spot[i]); }
    const float lvl = std::max(0.0f, (soc_pct / 100.0f - s_p.min_soc) * s_p.capacity_kwh);
    plan_controller(n, slot_min, clk, cost, st, fc_load, fc_solar, lvl, &s_fc);
    for (int i = 0; i < s_fc.n_prog; i++) prog_out[i] = s_fc.prog[i];
    for (int i = 0; i < n; i++) ev_out[i] = s_fc.ev_amps[i];
    *value_out = s_fc.value;
    return s_fc.n_prog;
}

extern "C" {

EMSCRIPTEN_KEEPALIVE float* bt_in_ptr() { return s_in; }
EMSCRIPTEN_KEEPALIVE int bt_in_stride() { return N; }
EMSCRIPTEN_KEEPALIVE float* bt_out_ptr() { return s_out; }
EMSCRIPTEN_KEEPALIVE int* bt_seg_ptr() { return s_seg; }
EMSCRIPTEN_KEEPALIVE uint16_t* bt_regs_ptr() { return s_regs; }
EMSCRIPTEN_KEEPALIVE int* bt_ev_ptr() { return s_ev; }
EMSCRIPTEN_KEEPALIVE int* bt_charge_ptr() { return s_charge; }
EMSCRIPTEN_KEEPALIVE float* bt_buy_ptr() { return s_buy; }
EMSCRIPTEN_KEEPALIVE float* bt_exp_ptr() { return s_exp; }

// Battery / fuse / planner parameters (energikalkyl units: kWh, kW, %, SEK).
EMSCRIPTEN_KEEPALIVE
void bt_set_battery(float capacity_kwh, float max_charge_kw, float max_discharge_kw, float efficiency,
                    float min_soc_pct, float max_soc_pct, float min_spread_sek, int segments) {
    s_p.capacity_kwh = capacity_kwh;
    s_p.max_charge_kw = max_charge_kw;
    s_p.max_discharge_kw = max_discharge_kw;
    s_p.efficiency = efficiency;
    s_p.min_soc = min_soc_pct / 100.0f;
    s_p.max_soc = max_soc_pct / 100.0f;
    s_p.min_spread = min_spread_sek;
    s_p.segments = std::max(1, std::min(MAX_PROG_SEGMENTS, segments));
}

// grid_max_kw = fuse A × phases × V × phase balance / 1000 (energikalkyl
// BatteryConfig.grid_max_kw); base_load_kw = the firmware's planning
// reserve (BASE_LOAD_KW) that pipeline_prepare_day subtracts.
EMSCRIPTEN_KEEPALIVE
void bt_set_grid(float grid_max_kw, float base_load_kw, int use_fw_tariff,
                 int export_enabled, float export_factor, float export_fee_sek) {
    s_p.grid_max_kw = grid_max_kw;
    s_p.base_load_kw = base_load_kw;
    s_p.use_fw_tariff = use_fw_tariff != 0;
    s_p.export_enabled = export_enabled != 0;
    s_p.export_factor = export_factor;
    s_p.export_fee = export_fee_sek;
}

// mode: EvPriorityMode (0 = battery first, 1 = EV first, 2 = auto)
EMSCRIPTEN_KEEPALIVE
void bt_set_ev(int enabled, int win_start_h, int win_end_h, float daily_kwh, int mode) {
    s_p.ev_enabled = enabled != 0;
    s_p.ev_win_start = win_start_h;
    s_p.ev_win_end = win_end_h;
    s_p.ev_daily_kwh = daily_kwh;
    s_p.ev_mode = (mode == 1) ? EV_PRIO_EV_FIRST : (mode == 2) ? EV_PRIO_AUTO : EV_PRIO_BATTERY_FIRST;
}

// Reset all parameters to config.h values.
EMSCRIPTEN_KEEPALIVE void bt_defaults() { s_p = Params{}; }

// Plan one day. Inputs in bt_in_ptr(); levels are kWh above the SOC floor
// carried from the previous day of each reference chain; ctrl_soc_pct is the
// simulated Deye's SOC at local midnight. forecast_is_perfect skips the
// duplicate ctrlmodel computation. Returns the number of program points.
//
// bt_out_ptr(): [0..5] ideal, [6..11] progperf, [12..17] ctrlperf,
//   [18..23] ctrlmodel (each: net, charge_cost, discharge_value, in, out,
//   end_level), [24] expected plan value, [25] n_prog, [26] EV planned kWh,
//   [27] battery grid-charge kW, [28] fuse budget kW, [29] grid charge A,
//   [30] EV first (order chosen), [31] both orders compared (auto),
//   [32] gain of the chosen order vs the other (SEK, ≥ 0)
EMSCRIPTEN_KEEPALIVE
int bt_plan_day(int y, int m, int d, int n, int slot_min,
                float lvl_ideal, float lvl_progperf, float lvl_ctrlperf, float lvl_ctrlmodel,
                float ctrl_soc_pct, int forecast_is_perfect) {
    if (n <= 0 || n > N || slot_min <= 0) return -1;
    std::memset(s_out, 0, sizeof(s_out));
    const float slot_h = static_cast<float>(slot_min) / 60.0f;
    LocalDate ld; ld.year = y; ld.month = m; ld.day = d;
    const DaySlotClock clk = day_slot_clock_for(ld, slot_min, n);
    static int start_min[N];
    const float* spot = s_in + IN_SPOT * N;
    if (s_p.use_fw_tariff) {
        scheduler_day_buy_costs(spot, n, slot_min, y, m, d, s_buy);
    } else {
        for (int i = 0; i < n; i++) s_buy[i] = s_in[IN_BUY * N + i];
    }
    for (int i = 0; i < n; i++) {
        start_min[i] = slot_local_start_min(&clk, i);
        s_exp[i] = s_p.export_enabled
            ? std::max(0.0f, spot[i] * s_p.export_factor - s_p.export_fee) : 0.0f;
    }
    const float* house = s_in + IN_HOUSE * N;
    const float* solar = s_in + IN_SOLAR * N;
    const float* ev_calc = s_in + IN_EV_CALC * N;
    const PlanParams pp = plan_params(slot_h);

    /* ideal + progperf: the calculator's view (EV inside the load) */
    static PlanSlot act[N];
    for (int i = 0; i < n; i++) {
        PlanSlot x;
        x.buy_cost = s_buy[i];
        x.export_value = s_exp[i];
        x.load_kwh = house[i] + ev_calc[i];
        x.solar_kwh = solar[i];
        x.grid_room_kwh = std::max(0.0f, std::min(s_p.max_charge_kw, s_p.grid_max_kw - x.load_kwh / slot_h)) * slot_h;
        act[i] = x;
    }
    static BatteryPlan plan_i;
    bat_plan_day(act, n, 0, pp, lvl_ideal, &plan_i);
    put_money(0, bat_execute_plan(&plan_i, act, n, pp, lvl_ideal));
    static BatteryPlan plan_p;
    static PlanSegment segs_p[N];
    bat_plan_day(act, n, 0, pp, lvl_progperf, &plan_p);
    const int nsp = bat_plan_program(&plan_p, act, 0, pp, s_p.segments, segs_p);
    put_money(6, bat_simulate_program(segs_p, nsp, act, n, 0, pp, lvl_progperf));

    /* controller structure, actual house (no EV), executed on actual data */
    plan_controller(n, slot_min, clk, s_buy, start_min, house, solar, lvl_ctrlperf, &s_perf);
    // Execute on actual slots: same PlanSlots as planned (perfect forecast)
    put_money(12, bat_simulate_program(s_perf.segs, s_perf.ns, s_perf.ps, n, 0, pp, lvl_ctrlperf));

    /* controller with its forecast → this is the program the Deye runs */
    const float ctrl_level = std::max(0.0f, (ctrl_soc_pct / 100.0f - s_p.min_soc) * s_p.capacity_kwh);
    const CtrlPlan* run = &s_perf;
    if (!forecast_is_perfect || std::fabs(ctrl_level - lvl_ctrlperf) > 1e-3f) {
        plan_controller(n, slot_min, clk, s_buy, start_min, s_in + IN_FC_HOUSE * N,
                        s_in + IN_FC_SOLAR * N, ctrl_level, &s_fc);
        run = &s_fc;
    }
    // ctrlmodel: firmware Deye model of that program on the ACTUAL day. The
    // Deye self-uses against everything on its CT: the actual house plus,
    // when the go-e is behind the CT, the EV draw of the program it runs.
    static PlanSlot actual_house[N];
    for (int i = 0; i < n; i++) {
        actual_house[i] = s_perf.ps[i];          // actual solar, perfect-plan room
        actual_house[i].load_kwh = house[i] + (run->sp.ct_sees_ev ? run->sp.ev_e_kwh[i] : 0.0f);
        const float ev = run->ev_amps[i] * static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE / 1000.0f;
        const float room = std::min(run->bat_charge_kw, s_p.grid_max_kw - house[i] / slot_h - ev);
        actual_house[i].grid_room_kwh = std::max(0.0f, room) * slot_h;
    }
    put_money(18, bat_simulate_program(run->segs, run->ns, actual_house, n, 0, pp, lvl_ctrlmodel));

    s_out[24] = run->value;
    s_out[25] = static_cast<float>(run->n_prog);
    s_out[26] = run->ev_kwh;
    s_out[27] = run->bat_charge_kw;
    s_out[28] = run->fuse_avail;
    s_out[30] = run->sp.ev_first ? 1.0f : 0.0f;
    s_out[31] = run->sp.compared ? 1.0f : 0.0f;
    s_out[32] = run->sp.compared ? run->sp.other_total_sek - run->sp.total_sek : 0.0f;
    int max_w = 0;
    for (int k = 0; k < run->n_prog; k++) {
        s_seg[k] = run->prog[k].start_min;
        s_seg[MAX_PROG_SEGMENTS + k] = run->prog[k].grid_charge ? 1 : 0;
        s_seg[2 * MAX_PROG_SEGMENTS + k] = run->prog[k].soc;
        s_seg[3 * MAX_PROG_SEGMENTS + k] = run->prog[k].power_w;
        if (run->prog[k].grid_charge) max_w = std::max(max_w, run->prog[k].power_w);
    }
    const int amps = deye_grid_charge_current_a(static_cast<float>(max_w) / 1000.0f, BATTERY_CHARGE_V_MAX,
                                                DEYE_INVERTER_EFF, DEYE_GRID_CHARGE_MAX_A);
    s_out[29] = static_cast<float>(amps);
    DeyeProgram p;
    if (run->n_prog > 0 &&
        deye_build_program_segments(run->prog, run->n_prog, static_cast<int>(std::lround(s_p.min_soc * 100.0f)),
                                    DEYE_PROG_IDLE_POWER_W, amps, &p)) {
        for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
            s_regs[i] = p.time_hhmm[i];
            s_regs[6 + i] = p.power_w[i];
            s_regs[12 + i] = p.soc[i];
            s_regs[18 + i] = p.charge[i];
        }
        s_regs[24] = p.tou_enable;
        s_regs[25] = p.grid_charge_enable;
        s_regs[26] = p.grid_charge_current_a;
    } else {
        deye_safe_program(static_cast<int>(std::lround(s_p.min_soc * 100.0f)), DEYE_PROG_IDLE_POWER_W, &p);
        for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
            s_regs[i] = p.time_hhmm[i]; s_regs[6 + i] = p.power_w[i];
            s_regs[12 + i] = p.soc[i]; s_regs[18 + i] = p.charge[i];
        }
        s_regs[24] = p.tou_enable; s_regs[25] = p.grid_charge_enable; s_regs[26] = p.grid_charge_current_a;
    }
    for (int i = 0; i < n; i++) {
        s_ev[i] = run->ev_amps[i];
        s_charge[i] = run->plan[i] ? 1 : 0;
    }
    return run->n_prog;
}

}  // extern "C"
