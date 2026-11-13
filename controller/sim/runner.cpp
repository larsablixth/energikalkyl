// ── Whole-period runs of the NORVI's controller in the C++ world ───────────
//
// Used by the year batch / "Validate calculator" (browser Web Worker, WASM),
// `make validate` and energikalkyl's controller check (native). Each run:
//   1. the period's days are loaded (run_add_day): spot prices, house load
//      and solar per slot, optionally the calculator's own buying cost and
//      the outdoor temperature;
//   2. the installation is set (run_set_plant → firmware plant.h): battery,
//      inverter, fuse, house reserve, EV, solar kWp, grid fees;
//   3. run_days() moves the clock minute by minute from local midnight of
//      the first day: the controller (firmware controller.cpp, via
//      controller_hal.cpp with the C++ world as its devices) runs every tick
//      that is due — it fetches prices at 13:30, plans, writes the Deye
//      program, sets the go-e, guards the fuse — and the world (world.h)
//      executes what it wrote for that minute.
// Nothing here decides anything: the runner only feeds data and moves time.
//
// Money as energikalkyl: buying cost per slot = the calculator's own cost if
// given, else the firmware's (spot × VAT + plant grid fee); battery kr =
// discharge value − grid-charge cost; zero export.

#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <vector>
#include <algorithm>

#include "config.h"
#include "plant.h"
#include "controller.h"
#include "scheduler.h"
#include "time_local.h"
#include "sim_devices.h"
#include "world.h"

extern "C" {
void ctrl_reset(double now_utc);
void ctrl_tick(double now_utc, int force_fetch);
void ctrl_set_n_flex(int n);
}

namespace {

struct Day {
    int y = 0, m = 0, d = 0, n = 0, slot_min = 60;
    std::vector<float> spot, buy, house, solar, temp, ev_calc;
    bool has_buy = false, has_temp = false;
};

// Per-day result (run_day_result): RR_* indices
enum {
    RR_BATTERY_KR, RR_CHARGE_COST, RR_DISCHARGE_VALUE, RR_IN_KWH, RR_OUT_KWH,
    RR_SOLAR_TO_BAT, RR_SOLAR_SELF_KWH, RR_SOLAR_SELF_KR, RR_CURTAILED, RR_EV_KWH,
    RR_EV_KR, RR_EV_UNMET, RR_IMPORT_KWH, RR_BILL_KR, RR_HOUSE_KWH, RR_END_SOC,
    RR_PROGRAM_WRITES, RR_GUARD_MAX_LEVEL, RR_GUARD_EVENTS, RR_BAT_PAUSED_MIN,
    RR_GOE_CAPPED_MIN, RR_SAFE_MIN, RR_PLAN_VALUE, RR_N_PROG, RR_LOOKAHEAD_GAIN,
    RR_HOUSE_FIT, RR_FC_LOAD_KWH, RR_N
};

std::vector<Day> g_days;
float g_buf[8 * MAX_SLOTS];                // JS writes one day here (run_day_buffer)
std::vector<float> g_results;              // RR_N per day
int  g_done = 0;
bool g_started = false;
double g_now = 0;

// options
Plant g_plant;
float g_start_soc = -1;                    // < 0 = min SOC
bool  g_realistic = false;
int   g_step_s = 60;
bool  g_verbose = false;
float g_shares[3] = {0.43f, 0.33f, 0.24f};

// world
DeyeWorld  g_deye;
GoeWorld   g_goe;
MeterWorld g_meter;
int g_writes = 0;

int day_index(int y, int m, int d) {
    for (size_t i = 0; i < g_days.size(); i++) {
        if (g_days[i].y == y && g_days[i].m == m && g_days[i].d == d) return static_cast<int>(i);
    }
    return -1;
}

// ── The C++ world as the controller's devices ─────────────────────────────
bool w_read_soc(float* s) { *s = g_deye.soc; return true; }
int w_fetch_prices(int y, int m, int d, float* out, int max_slots, int* slot_min) {
    const int i = day_index(y, m, d);
    if (i < 0) return 0;
    const Day& day = g_days[i];
    const int n = std::min(day.n, max_slots);
    for (int k = 0; k < n; k++) out[k] = day.spot[k];
    *slot_min = day.slot_min;
    return n;
}
bool w_forecast(int which, double day_start_utc, int, int n, int, float* out) {
    if (which != 2) return false;            // the controller asks only for temperature
    const LocalDate ld = local_date_of(static_cast<time_t>(day_start_utc));
    const int i = day_index(ld.year, ld.month, ld.day);
    if (i < 0 || !g_days[i].has_temp) return false;
    for (int k = 0; k < n; k++) out[k] = k < g_days[i].n ? g_days[i].temp[k] : NAN;
    return true;
}
bool w_write_program(const uint16_t* regs) { g_deye.write_program(regs); g_writes++; return true; }
bool w_read_live(HalLive* o) {
    o->grid_w = g_deye.grid_draw_kw * 1000.0f;
    o->load_w = g_deye.load_kw * 1000.0f;
    o->pv_w = g_deye.pv_kw * 1000.0f;
    o->soc = g_deye.soc;
    o->bat_w = -(g_deye.solar_charge_kw + g_deye.grid_charge_kw - g_deye.served_kw) * 1000.0f;
    return true;
}
bool w_read_meter(HalMeter* o) {
    o->l1_a = g_meter.l1; o->l2_a = g_meter.l2; o->l3_a = g_meter.l3; o->power_w = g_meter.power_w;
    return true;
}
bool w_goe_status(HalGoe* o) {
    o->connected = g_goe.car_connected;
    o->amps = g_goe.amps;
    o->soc = -1.0f;
    return true;
}
bool w_goe_set_amps(int a) { g_goe.set_amps(a); return true; }
bool w_flex_set(int, bool) { return true; }
// Quiet unless verbose: the last day always logs "no prices for tomorrow"
// (the period ends), and SAFE time / unmet EV are in the day results.
void w_log(const char* level, const char* msg) {
    if (g_verbose) std::printf("    [%s] %s\n", level, msg);
}

SimDevices world_devices() {
    SimDevices d;
    d.read_soc = w_read_soc;
    d.fetch_prices = w_fetch_prices;
    d.forecast = w_forecast;
    d.write_program = w_write_program;
    d.read_live = w_read_live;
    d.read_meter = w_read_meter;
    d.goe_status = w_goe_status;
    d.goe_set_amps = w_goe_set_amps;
    d.flex_set = w_flex_set;
    d.log = w_log;
    return d;
}

bool in_window(int hour, int start, int end) {
    return start <= end ? (hour >= start && hour < end) : (hour >= start || hour < end);
}

void start() {
    *plant_mutable() = g_plant;
    const Plant& p = plant();
    g_deye = DeyeWorld{};
    g_deye.capacity_kwh = p.battery_capacity_kwh;
    g_deye.min_soc = static_cast<float>(p.battery_min_soc);
    g_deye.max_soc = static_cast<float>(p.battery_max_soc);
    g_deye.max_charge_kw = std::min(p.inverter_max_bat_kw, p.battery_charge_kw);
    g_deye.max_discharge_kw = p.inverter_max_bat_kw;
    g_deye.efficiency = p.battery_efficiency;
    g_deye.realistic = g_realistic;
    g_deye.soc = g_start_soc >= 0 ? g_start_soc : static_cast<float>(p.battery_min_soc);
    g_goe = GoeWorld{};
    g_goe.min_amps = GOE_MIN_AMPS;
    g_goe.max_amps = GOE_MAX_AMPS;
    g_meter = MeterWorld{};
    for (int k = 0; k < 3; k++) g_meter.shares[k] = g_shares[k];
    g_writes = 0;
    g_done = 0;
    g_results.assign(g_days.size() * RR_N, 0.0f);
    const SimDevices dev = world_devices();
    sim_set_devices(&dev);
    LocalDate ld; ld.year = g_days[0].y; ld.month = g_days[0].m; ld.day = g_days[0].d;
    g_now = static_cast<double>(local_midnight_utc(ld));
    ctrl_reset(g_now);
    ctrl_set_n_flex(0);
    g_started = true;
}

void run_one_day(int di) {
    const Day& day = g_days[di];
    float* r = &g_results[static_cast<size_t>(di) * RR_N];
    LocalDate ld; ld.year = day.y; ld.month = day.m; ld.day = day.d;
    const DaySlotClock clk = day_slot_clock_for(ld, day.slot_min, day.n);
    static float buy[MAX_SLOTS];
    if (day.has_buy) {
        for (int i = 0; i < day.n; i++) buy[i] = day.buy[i];
    } else {
        scheduler_day_buy_costs(day.spot.data(), day.n, day.slot_min, day.y, day.m, day.d, buy);
    }
    const Plant& p = plant();
    const bool ct_ev = DEYE_CT_SEES_GOE;
    g_goe.need_kwh = p.ev_daily_kwh > 0 ? p.ev_daily_kwh : 0.0f;
    const double t0 = static_cast<double>(clk.day_start_utc);
    const double t1 = t0 + static_cast<double>(day.n) * day.slot_min * 60.0;
    const int writes0 = g_writes;
    int last_level = 0;
    const float dt_h = g_step_s / 3600.0f;
    for (double t = t0; t < t1 - 1e-6; t += g_step_s) {
        g_now = t;
        ctrl_tick(t, 0);                                  // the controller, on the world as it is
        const ControllerView& v = controller_view();
        const int slot = std::min(day.n - 1, static_cast<int>((t - t0) / (day.slot_min * 60.0)));
        struct tm lt;
        time_to_local(static_cast<time_t>(t), &lt);
        const int minute = lt.tm_hour * 60 + lt.tm_min;
        const float slot_h = day.slot_min / 60.0f;
        const float house_kw = day.house[slot] / slot_h;
        const float solar_kw = day.solar[slot] / slot_h;
        g_goe.car_connected = p.ev_daily_kwh > 0 && in_window(lt.tm_hour, p.ev_window_start_h, p.ev_window_end_h);
        const float ev_kw = g_goe.tick(dt_h);
        g_deye.tick(minute, dt_h, house_kw + (ct_ev ? ev_kw : 0.0f), solar_kw, true);
        g_meter.update(house_kw, g_deye.grid_draw_kw, ev_kw, ct_ev);
        // accounting
        const float b = buy[slot];
        auto e = [&](float kw) { return kw * dt_h; };
        r[RR_IN_KWH] += e(g_deye.grid_charge_kw);
        r[RR_CHARGE_COST] += e(g_deye.grid_charge_kw) * b;
        r[RR_OUT_KWH] += e(g_deye.served_kw);
        r[RR_DISCHARGE_VALUE] += e(g_deye.served_kw) * b;
        r[RR_SOLAR_TO_BAT] += e(g_deye.solar_charge_kw);
        r[RR_SOLAR_SELF_KWH] += e(g_deye.solar_direct_kw);
        r[RR_SOLAR_SELF_KR] += e(g_deye.solar_direct_kw) * b;
        r[RR_CURTAILED] += e(g_deye.curtailed_kw);
        r[RR_EV_KWH] += e(ev_kw);
        r[RR_EV_KR] += e(ev_kw) * b;
        const float imp = std::max(0.0f, g_deye.grid_draw_kw + (ct_ev ? 0.0f : ev_kw));
        r[RR_IMPORT_KWH] += e(imp);
        r[RR_BILL_KR] += e(imp) * b;
        r[RR_HOUSE_KWH] += e(house_kw);
        const int level = v.guard.shed_level;
        if (level > last_level) r[RR_GUARD_EVENTS] += 1;
        last_level = level;
        r[RR_GUARD_MAX_LEVEL] = std::max(r[RR_GUARD_MAX_LEVEL], static_cast<float>(level));
        if (v.guard_bat_inhibit) r[RR_BAT_PAUSED_MIN] += g_step_s / 60.0f;
        if (v.guard_goe_cap >= 0) r[RR_GOE_CAPPED_MIN] += g_step_s / 60.0f;
        if (v.safe_hold) r[RR_SAFE_MIN] += g_step_s / 60.0f;
    }
    g_now = t1;
    r[RR_BATTERY_KR] = r[RR_DISCHARGE_VALUE] - r[RR_CHARGE_COST];
    r[RR_EV_UNMET] = g_goe.need_kwh;
    r[RR_END_SOC] = g_deye.soc;
    r[RR_PROGRAM_WRITES] = static_cast<float>(g_writes - writes0);
    const ControllerView& v = controller_view();
    if (v.today_valid && v.today->year == day.y && v.today->month == day.m && v.today->day == day.d) {
        r[RR_PLAN_VALUE] = v.today->plan_value_sek;
        r[RR_N_PROG] = static_cast<float>(v.today->n_prog);
        r[RR_LOOKAHEAD_GAIN] = v.today->lookahead_gain_sek;
        r[RR_HOUSE_FIT] = static_cast<float>(v.today->fc_house_fit);
        r[RR_FC_LOAD_KWH] = v.today->fc_load_day_kwh;
    }
}

}  // namespace

extern "C" {

// Clear the period (days and results).
EMSCRIPTEN_KEEPALIVE void run_reset() {
    g_days.clear();
    g_results.clear();
    g_done = 0;
    g_started = false;
    g_plant = Plant{};
    g_start_soc = -1;
    g_realistic = false;
    g_step_s = 60;
}

// The installation for the run (firmware plant.h). min/max SOC in %.
EMSCRIPTEN_KEEPALIVE
void run_set_plant(float battery_kwh, float inverter_kw, float efficiency, int min_soc, int max_soc,
                   int fuse_amps, float base_load_kw, float ev_kwh_day, int ev_start_h, int ev_end_h,
                   float solar_kwp, float fee_high, float fee_low, float min_spread) {
    g_plant = Plant{};
    g_plant.battery_capacity_kwh = battery_kwh;
    g_plant.inverter_max_bat_kw = inverter_kw;
    g_plant.battery_charge_kw = std::max(inverter_kw, g_plant.battery_charge_kw);
    g_plant.battery_efficiency = efficiency;
    g_plant.battery_min_soc = min_soc;
    g_plant.battery_max_soc = max_soc;
    g_plant.fuse_nominal_amps = fuse_amps;
    g_plant.base_load_kw = base_load_kw;
    g_plant.ev_daily_kwh = ev_kwh_day;
    g_plant.ev_window_start_h = ev_start_h;
    g_plant.ev_window_end_h = ev_end_h;
    g_plant.solar_kwp = solar_kwp;
    g_plant.grid_fee_high_sek = fee_high;
    g_plant.grid_fee_low_sek = fee_low;
    g_plant.min_spread_sek = min_spread;
}

// Battery/EV fuse-budget order (firmware EvPriorityMode: 0 battery first,
// 1 EV first, 2 auto). Call after run_set_plant.
EMSCRIPTEN_KEEPALIVE void run_set_ev_mode(int mode) {
    if (mode >= 0 && mode <= 2) g_plant.ev_priority_mode = mode;
}

// start_soc < 0 = the minimum SOC; realistic = the "realistic" loss model;
// step_s = world step (60 s default; the controller's ticks run at their own
// periods inside each step).
EMSCRIPTEN_KEEPALIVE
void run_set_options(float start_soc, int realistic, int step_s, float s1, float s2, float s3, int verbose) {
    g_start_soc = start_soc;
    g_realistic = realistic != 0;
    g_step_s = std::max(5, std::min(900, step_s));
    if (s1 + s2 + s3 > 0.5f) { g_shares[0] = s1; g_shares[1] = s2; g_shares[2] = s3; }
    g_verbose = verbose != 0;
}

// One day's inputs are written here before run_add_day: rows of MAX_SLOTS
// floats: 0 spot SEK/kWh excl. VAT, 1 buying cost SEK/kWh (has_buy),
// 2 house kWh per slot (behind the Deye, no EV), 3 solar kWh per slot,
// 4 outdoor °C (has_temp), 5 EV kWh inside the calculator's load (info).
EMSCRIPTEN_KEEPALIVE float* run_day_buffer() { return g_buf; }
EMSCRIPTEN_KEEPALIVE int run_buffer_stride() { return MAX_SLOTS; }

// Days must be added in date order, without gaps. Returns the day count.
EMSCRIPTEN_KEEPALIVE
int run_add_day(int y, int m, int d, int n, int slot_min, int has_buy, int has_temp) {
    if (n <= 0 || n > MAX_SLOTS || slot_min <= 0) return -1;
    Day day;
    day.y = y; day.m = m; day.d = d; day.n = n; day.slot_min = slot_min;
    day.has_buy = has_buy != 0;
    day.has_temp = has_temp != 0;
    const int S = MAX_SLOTS;
    day.spot.assign(g_buf, g_buf + n);
    day.buy.assign(g_buf + S, g_buf + S + n);
    day.house.assign(g_buf + 2 * S, g_buf + 2 * S + n);
    day.solar.assign(g_buf + 3 * S, g_buf + 3 * S + n);
    day.temp.assign(g_buf + 4 * S, g_buf + 4 * S + n);
    day.ev_calc.assign(g_buf + 5 * S, g_buf + 5 * S + n);
    g_days.push_back(day);
    g_started = false;
    return static_cast<int>(g_days.size());
}

// Run the next `count` days (the first call starts the controller at local
// midnight of the first day). Returns the number of days run so far.
EMSCRIPTEN_KEEPALIVE
int run_days(int count) {
    if (g_days.empty()) return 0;
    if (!g_started) start();
    for (int k = 0; k < count && g_done < static_cast<int>(g_days.size()); k++) {
        run_one_day(g_done);
        g_done++;
    }
    return g_done;
}

EMSCRIPTEN_KEEPALIVE int run_result_stride() { return RR_N; }
EMSCRIPTEN_KEEPALIVE float* run_day_result(int i) {
    if (i < 0 || static_cast<size_t>(i) * RR_N >= g_results.size()) return nullptr;
    return &g_results[static_cast<size_t>(i) * RR_N];
}
EMSCRIPTEN_KEEPALIVE int run_house_days() {
    const ControllerView& v = controller_view();
    return v.house_learn ? static_cast<int>(v.house_learn->days) : 0;
}

}  // extern "C"
