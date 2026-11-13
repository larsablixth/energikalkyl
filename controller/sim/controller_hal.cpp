// ── The simulator side of the controller: clock + simulated devices ───────
//
// The controller itself is the firmware's controller.cpp (every decision the
// NORVI makes). This file only:
//   1. moves the clock: ctrl_tick(now) runs the controller's ticks that are
//      due on the simulated clock — scheduler every SCHED_POLL_MS, fuse guard
//      every FUSE_GUARD_POLL_MS, surplus every SURPLUS_POLL_MS — exactly the
//      periods of the NORVI's FreeRTOS tasks (main.cpp);
//   2. plays the devices the controller talks to (ControllerHw): each hook
//      does what the real driver does (deye_modbus.cpp: build the register
//      image with the firmware's deye_build_* and write it; goe_rest.cpp;
//      the P1 meter; relays) against the JS world via sim_hal.h;
//   3. reports plan/status as JSON for the UI.
// It contains no control rule: no planning, no decision when to fetch, swap
// or re-plan, no safety logic — that is all firmware code.
//
// Not simulated: the SD card (what the controller learns is kept in memory
// for the session; ctrl_reset = power-on with nothing learned), settings.txt
// (config.h defaults), NTP/RTC (the sim clock is always valid).

#include <emscripten/emscripten.h>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <cstdarg>
#include <algorithm>
#include <ctime>

#include "config.h"
#include "controller.h"
#include "pipeline.h"
#include "scheduler.h"
#include "deye_program.h"
#include "time_local.h"
#include "sim_hal.h"
#include "sim_devices.h"

namespace {

// ── Devices: the JS world (default) or the C++ world (sim_set_devices) ────
SimDevices js_devices() {
    SimDevices d;
    d.read_soc = hal_read_soc;
    d.fetch_prices = hal_fetch_prices;
    d.forecast = hal_forecast;
    d.write_program = hal_write_program;
    d.read_live = hal_read_live;
    d.read_meter = hal_read_meter;
    d.goe_status = hal_goe_status;
    d.goe_set_amps = hal_goe_set_amps;
    d.flex_set = hal_flex_set;
    d.log = hal_log;
    d.display = hal_display;
    return d;
}
SimDevices g_dev = js_devices();

void dev_log(const char* level, const char* msg) { if (g_dev.log) g_dev.log(level, msg); }

// ── Clock ─────────────────────────────────────────────────────────────────
double g_now_utc = 0.0;
time_t   hw_now_utc() { return static_cast<time_t>(g_now_utc); }
uint32_t hw_now_ms()  { return static_cast<uint32_t>(static_cast<uint64_t>(g_now_utc * 1000.0)); }

// ── Inverter (as deye_modbus.cpp: build with the firmware, then write) ─────
DeyeProgram g_prog;
bool g_state_known = false;        // a program has been verified (as the driver's s_state_known)
int  g_modbus_failures = 0;
int  g_n_program_writes = 0;

bool write_program(const DeyeProgram& p) {
    uint16_t regs[HAL_PROGRAM_REGS];
    for (int i = 0; i < DEYE_N_PROGRAMS; i++) {
        regs[i] = p.time_hhmm[i];
        regs[6 + i] = p.power_w[i];
        regs[12 + i] = p.soc[i];
        regs[18 + i] = p.charge[i];
    }
    regs[24] = p.tou_enable;
    regs[25] = p.grid_charge_enable;
    regs[26] = p.grid_charge_current_a;
    g_state_known = false;            // as the driver: unknown while writing
    if (!g_dev.write_program(regs)) {
        g_modbus_failures++;
        dev_log("ERROR", "Deye: program FAILED");
        return false;
    }
    g_prog = p;
    g_state_known = true;
    g_modbus_failures = 0;
    g_n_program_writes++;
    return true;
}

bool hw_deye_read_soc(float* soc) { return g_dev.read_soc(soc); }

bool hw_deye_read_power_status(DeyePowerStatus* out) {
    HalLive l;
    if (!g_dev.read_live(&l)) return false;
    *out = DeyePowerStatus{};
    out->battery_soc = l.soc;
    out->battery_power_w = l.bat_w;
    out->grid_power_w = l.grid_w;
    out->load_power_w = l.load_w;
    out->pv_power_w = l.pv_w;
    return true;
}
bool hw_deye_sample_power_status(DeyePowerStatus* out) { return hw_deye_read_power_status(out); }

bool hw_deye_set_program_segments(const ProgSegment* segs, int n, int grid_charge_a) {
    DeyeProgram p;
    if (!deye_build_program_segments(segs, n, BATTERY_MIN_SOC, DEYE_PROG_IDLE_POWER_W, grid_charge_a, &p)) {
        dev_log("ERROR", "Deye: invalid program segments — not written");
        return false;
    }
    return write_program(p);
}

bool hw_deye_set_charge_windows(const TouWindow* w, int n, int grid_charge_a) {
    DeyeProgram p;
    if (!deye_build_program(w, n, BATTERY_MIN_SOC, DEYE_PROG_IDLE_POWER_W, grid_charge_a, &p)) {
        dev_log("ERROR", "Deye: invalid charge windows — not written");
        return false;
    }
    return write_program(p);
}

bool hw_deye_set_charge(int start_min, int end_min, int target_soc) {
    TouWindow w;
    w.start_min = start_min;
    w.end_min = end_min;
    w.target_soc = target_soc;
    return hw_deye_set_charge_windows(&w, 1, 0);
}

bool hw_deye_set_idle() {
    DeyeProgram p;
    deye_safe_program(BATTERY_MIN_SOC, DEYE_PROG_IDLE_POWER_W, &p);
    return write_program(p);
}

bool hw_deye_apply_safe_program() {
    const bool ok = hw_deye_set_idle();
    dev_log(ok ? "INFO" : "ERROR", ok ? "Deye: SAFE program verified (no grid charge, self-use)"
                                      : "Deye: SAFE program write FAILED");
    return ok;
}

// As the driver: unknown (nothing verified yet) counts as "may be charging".
bool hw_deye_grid_charge_enabled() {
    return !g_state_known || deye_program_grid_charges(&g_prog);
}
int  hw_deye_consecutive_failures() { return g_modbus_failures; }
// The driver's cache only lets it skip an identical write; the sim always
// writes, so there is nothing to drop (the verified state is kept, as there).
void hw_deye_invalidate_cache() {}

// ── go-e ──────────────────────────────────────────────────────────────────
bool hw_goe_get_status(GoeStatus* out) {
    HalGoe g;
    if (!g_dev.goe_status(&g)) return false;
    out->car_connected = g.connected;
    out->charging = g.connected && g.amps > 0;
    out->current_amps = g.amps;
    out->force_state = g.amps > 0 ? 0 : 1;
    out->soc_percent = g.soc;
    return true;
}
bool hw_goe_set_amps(int amps) { return g_dev.goe_set_amps(amps); }
bool hw_goe_stop_charging() { return g_dev.goe_set_amps(0); }
bool hw_goe_release_stop() { return true; }   // the next set_amps resumes

// ── Prices, weather, meter, relays ────────────────────────────────────────
int hw_fetch_prices(int y, int m, int d, float* out, int max_slots, int* slot_min) {
    return g_dev.fetch_prices(y, m, d, out, max_slots, slot_min);
}

// SMHI's role: the world's outdoor temperature per slot (hal_forecast kind 2).
bool hw_forecast_temp(const DaySlotClock* clk, int month, float* out) {
    return g_dev.forecast(2, static_cast<double>(clk->day_start_utc), clk->slot_min, clk->n_slots,
                        month, out);
}

bool hw_read_meter(TibberPulseData* out) {
    HalMeter m;
    if (!g_dev.read_meter(&m)) return false;
    out->power_w = m.power_w;
    out->current_l1_a = m.l1_a;
    out->current_l2_a = m.l2_a;
    out->current_l3_a = m.l3_a;
    out->voltage_l1_v = out->voltage_l2_v = out->voltage_l3_v = FUSE_VOLTAGE;
    return fuse_guard_reading_valid(out);
}

bool g_flex_relay[MAX_FLEX_LOADS] = {};
bool hw_flex_set(const FlexLoadConfig*, int index, bool on) {
    if (index < 0 || index >= MAX_FLEX_LOADS) return false;
    if (!g_dev.flex_set(index, on)) return false;
    g_flex_relay[index] = on;
    return true;
}

// ── Storage (the SD card's role): in memory for this session ──────────────
uint8_t g_store[256];
int g_store_len = -1;
int hw_storage_read(const char*, uint8_t* buf, int max_len) {
    if (g_store_len < 0) return -1;
    const int n = std::min(g_store_len, max_len);
    std::memcpy(buf, g_store, n);
    return n;
}
bool hw_storage_write(const char*, const uint8_t* buf, int len) {
    if (len < 0 || len > static_cast<int>(sizeof(g_store))) return false;
    std::memcpy(g_store, buf, len);
    g_store_len = len;
    return true;
}

// ── Output ────────────────────────────────────────────────────────────────
void hw_log(const char* level, const char* msg) { dev_log(level, msg); }
void hw_show_status(const char* a, const char* b, const char* c, const char* d) { if (g_dev.display) g_dev.display(a, b, c, d); }
void hw_show_error(const char* msg) { dev_log("ERROR", msg); }

ControllerHw make_hw() {
    ControllerHw hw;
    hw.now_utc = hw_now_utc;
    hw.now_ms = hw_now_ms;
    hw.deye_read_soc = hw_deye_read_soc;
    hw.deye_read_power_status = hw_deye_read_power_status;
    hw.deye_sample_power_status = hw_deye_sample_power_status;
    hw.deye_set_program_segments = hw_deye_set_program_segments;
    hw.deye_set_charge_windows = hw_deye_set_charge_windows;
    hw.deye_set_charge = hw_deye_set_charge;
    hw.deye_set_idle = hw_deye_set_idle;
    hw.deye_apply_safe_program = hw_deye_apply_safe_program;
    hw.deye_grid_charge_enabled = hw_deye_grid_charge_enabled;
    hw.deye_consecutive_failures = hw_deye_consecutive_failures;
    hw.deye_invalidate_cache = hw_deye_invalidate_cache;
    hw.goe_get_status = hw_goe_get_status;
    hw.goe_set_amps = hw_goe_set_amps;
    hw.goe_stop_charging = hw_goe_stop_charging;
    hw.goe_release_stop = hw_goe_release_stop;
    hw.fetch_prices = hw_fetch_prices;
    hw.forecast_temp_c = hw_forecast_temp;
    hw.read_meter = hw_read_meter;
    hw.flex_set = hw_flex_set;
    hw.storage_read = hw_storage_read;
    hw.storage_write = hw_storage_write;
    hw.log_msg = hw_log;
    hw.show_status = hw_show_status;
    hw.show_error = hw_show_error;
    return hw;
}

// ── Power-on (main.cpp setup(): controller_init + boot safe program) ──────
FlexLoadConfig g_flex[MAX_FLEX_LOADS];
int  g_n_flex = 0;
bool g_flex_dirty = false;
bool g_booted = false;

void power_on() {
    g_prog = DeyeProgram{};
    g_state_known = false;
    g_modbus_failures = 0;
    for (int i = 0; i < MAX_FLEX_LOADS; i++) g_flex_relay[i] = false;
    const ControllerHw hw = make_hw();
    ControllerConfig cfg;
    cfg.flex_loads = g_flex;
    cfg.n_flex_loads = g_n_flex;
    controller_init(&hw, cfg);
    bool ok = false;
    for (int i = 0; i < DEYE_BOOT_SAFE_ATTEMPTS && !ok; i++) ok = controller_boot_safe();
    if (!ok) dev_log("ERROR", "Deye: safe program NOT confirmed at boot — retried by the scheduler");
    g_booted = true;
    g_flex_dirty = false;
}

// Task timing on the sim clock (last run of each task)
double g_last_sched = -1.0, g_last_guard = -1.0, g_last_surplus = -1.0;

// Run one task's ticks that are due up to `now`, at most `cap` per call (a
// long sim step would only repeat the same readings).
template <typename F>
void run_due(double now, double period_s, double* last, int cap, F tick) {
    if (*last < 0 || now < *last) *last = now - period_s;
    int k = 0;
    while (now - *last >= period_s && k < cap) {
        *last += period_s;
        g_now_utc = std::min(now, *last);
        tick();
        k++;
    }
    if (now - *last >= period_s) *last = now;
    g_now_utc = now;
}

// ── JSON for the UI ───────────────────────────────────────────────────────
char g_json[24576];

int jappend(int pos, const char* fmt, ...) __attribute__((format(printf, 2, 3)));
int jappend(int pos, const char* fmt, ...) {
    if (pos < 0 || pos >= static_cast<int>(sizeof(g_json)) - 1) return pos;
    va_list ap;
    va_start(ap, fmt);
    const int n = vsnprintf(g_json + pos, sizeof(g_json) - pos, fmt, ap);
    va_end(ap);
    if (n < 0) return pos;
    return std::min(pos + n, static_cast<int>(sizeof(g_json)) - 1);
}

}  // namespace

void sim_set_devices(const SimDevices* d) { g_dev = d ? *d : js_devices(); }

// ═════════════════════════════════════════════════════════════════════════
// Exported API (sim-scheduler.js)
// ═════════════════════════════════════════════════════════════════════════
extern "C" {

// Power-on at now_utc: the controller starts with nothing (as after a
// reboot with an empty SD card) and writes the boot safe program.
EMSCRIPTEN_KEEPALIVE
void ctrl_reset(double now_utc) {
    time_local_init();
    g_now_utc = now_utc;
    g_store_len = -1;
    g_n_program_writes = 0;
    g_last_sched = g_last_guard = g_last_surplus = -1.0;
    power_on();
}

// Flex loads (surplus-activated relays). months_mask: bit0 = January. On the
// NORVI the flex table is fixed at boot, so a change restarts the controller
// at the next tick (what is learned in this session is kept).
EMSCRIPTEN_KEEPALIVE
void ctrl_set_n_flex(int n) {
    const int nn = (n < 0) ? 0 : (n > MAX_FLEX_LOADS ? MAX_FLEX_LOADS : n);
    if (nn != g_n_flex) g_flex_dirty = true;
    g_n_flex = nn;
}

EMSCRIPTEN_KEEPALIVE
void ctrl_set_flex(int i, const char* name, float power_kw, int months_mask, int priority) {
    if (i < 0 || i >= MAX_FLEX_LOADS) return;
    FlexLoadConfig c;
    std::snprintf(c.name, sizeof(c.name), "%s", name ? name : "flex");
    c.power_kw = power_kw;
    c.control_type = FLEX_CTRL_GPIO;
    c.gpio_pin = i;
    c.active_months = months_mask;
    c.priority = priority;
    c.sched_mode = FLEX_SCHED_SOLAR;
    if (std::strcmp(c.name, g_flex[i].name) != 0 || c.power_kw != g_flex[i].power_kw ||
        c.active_months != g_flex[i].active_months || c.priority != g_flex[i].priority) {
        g_flex_dirty = true;
    }
    g_flex[i] = c;
}

// One call per JS time step: moves the clock to now_utc and runs every task
// iteration that is due — scheduler every SCHED_POLL_MS, fuse guard every
// FUSE_GUARD_POLL_MS, surplus every SURPLUS_POLL_MS. force_fetch (the UI's
// old "run scheduler now") has no counterpart on the NORVI and is ignored:
// move the clock to 13:30 instead.
EMSCRIPTEN_KEEPALIVE
void ctrl_tick(double now_utc, int force_fetch) {
    (void)force_fetch;
    if (!g_booted) ctrl_reset(now_utc);
    if (g_flex_dirty) {
        g_now_utc = now_utc;
        dev_log("INFO", "Flex loads changed — controller restarted (the NORVI reads them at boot)");
        uint8_t keep[sizeof(g_store)];
        const int keep_len = g_store_len;
        std::memcpy(keep, g_store, sizeof(g_store));
        power_on();
        g_store_len = keep_len;
        std::memcpy(g_store, keep, sizeof(g_store));
    }
    run_due(now_utc, FUSE_GUARD_POLL_MS / 1000.0, &g_last_guard, 24, [] { controller_guard_tick(); });
    run_due(now_utc, SCHED_POLL_MS / 1000.0, &g_last_sched, 240, [] { controller_scheduler_tick(); });
    run_due(now_utc, SURPLUS_POLL_MS / 1000.0, &g_last_surplus, 8, [] { controller_surplus_tick(); });
}

// Plan of today (which = 0) or tomorrow (1) as JSON:
// {"valid":1,"date":"Y-M-D","slot_min":60,"n":24,"value":12.3,
//  "prices":[...],"buy":[...],"start_min":[...],"charge":[0/1...],
//  "ev_amps":[...],"ev_kwh":30,"prog":[{"start":0,"grid":0,"soc":15,"power":0},...]}
EMSCRIPTEN_KEEPALIVE
const char* ctrl_plan_json(int which) {
    const ControllerView& v = controller_view();
    const PipelineDayContext& c = which ? *v.tomorrow : *v.today;
    const bool valid = which ? v.tomorrow_valid : v.today_valid;
    int p = 0;
    if (!valid || c.n_prices <= 0) {
        jappend(p, "{\"valid\":0}");
        return g_json;
    }
    const int n = c.n_prices;
    static float buy[MAX_SLOTS];
    scheduler_day_buy_costs(c.prices, n, c.slot_duration_min, c.year, c.month, c.day, buy);
    const DaySlotClock clk = pipeline_day_clock(&c);
    p = jappend(p, "{\"valid\":1,\"date\":\"%04d-%02d-%02d\",\"slot_min\":%d,\"n\":%d,"
                   "\"value\":%.3f,\"written\":%d,\"bat_charge_kw\":%.3f,\"fuse_kw\":%.3f,\"ev_kwh\":%.2f,"
                   "\"ev_first\":%d,\"ev_order_compared\":%d,\"ev_order_gain\":%.2f,\"ev_absent\":%d,"
                   "\"load_kwh\":%.2f,\"temp_c\":%.1f,\"house_fit\":%d,\"lookahead_gain\":%.2f",
                c.year, c.month, c.day, c.slot_duration_min, n, c.plan_value_sek,
                c.tou_written ? 1 : 0, c.bat_charge_kw, c.fuse_available_kw, c.ev_planned_kwh,
                c.ev_first ? 1 : 0, c.ev_order_compared ? 1 : 0, c.ev_order_gain_sek, c.ev_absent ? 1 : 0,
                c.fc_load_day_kwh, c.fc_temp_mean_c, c.fc_house_fit, c.lookahead_gain_sek);
    const char* keys[5] = {"prices", "buy", "start_min", "charge", "ev_amps"};
    for (int k = 0; k < 5; k++) {
        p = jappend(p, ",\"%s\":[", keys[k]);
        for (int i = 0; i < n; i++) {
            const char* sep = i ? "," : "";
            switch (k) {
                case 0: p = jappend(p, "%s%.4f", sep, c.prices[i]); break;
                case 1: p = jappend(p, "%s%.4f", sep, buy[i]); break;
                case 2: p = jappend(p, "%s%d", sep, slot_local_start_min(&clk, i)); break;
                case 3: p = jappend(p, "%s%d", sep, c.plan[i] ? 1 : 0); break;
                default: p = jappend(p, "%s%d", sep, static_cast<int>(c.ev_amps[i])); break;
            }
        }
        p = jappend(p, "]");
    }
    p = jappend(p, ",\"prog\":[");
    for (int i = 0; i < c.n_prog; i++) {
        p = jappend(p, "%s{\"start\":%d,\"grid\":%d,\"soc\":%d,\"power\":%d}", i ? "," : "",
                    c.prog[i].start_min, c.prog[i].grid_charge ? 1 : 0, c.prog[i].soc, c.prog[i].power_w);
    }
    jappend(p, "]}");
    return g_json;
}

// Controller status for the UI.
EMSCRIPTEN_KEEPALIVE
const char* ctrl_status_json() {
    const ControllerView& v = controller_view();
    int p = 0;
    p = jappend(p, "{\"today_valid\":%d,\"tomorrow_valid\":%d,\"last_slot\":%d,\"safe_hold\":%d,"
                   "\"safe_reason\":\"%s\",\"guard_level\":%d,\"guard_util\":%.1f,\"guard_max_a\":%.2f,"
                   "\"guard_stale\":%d,\"goe_cap\":%d,\"goe_planned\":%d,\"goe_applied\":%d,"
                   "\"bat_inhibit\":%d,\"safe_pending\":%d,\"flex_inhibit\":%d,\"prog_writes\":%d,\"guard_steps\":%d,"
                   "\"surplus_polls\":%d,\"grid_charge_programmed\":%d,\"lookahead_pending\":%d,"
                   "\"house_days\":%u,\"flex\":[",
                v.today_valid ? 1 : 0, v.tomorrow_valid ? 1 : 0, v.last_slot, v.safe_hold ? 1 : 0,
                safety_action_name(v.safe_hold ? v.safe_reason : SAFETY_OK),
                v.guard.shed_level, v.guard.utilization_pct, v.guard.max_phase_a,
                v.guard.meter_stale ? 1 : 0, v.guard_goe_cap, v.goe_planned_amps,
                v.goe_applied_amps, v.guard_bat_inhibit ? 1 : 0, v.safe_pending ? 1 : 0, v.guard.hp_shed ? 1 : 0,
                g_n_program_writes, v.guard_ticks, v.surplus_ticks,
                hw_deye_grid_charge_enabled() ? 1 : 0, v.lookahead_pending ? 1 : 0,
                static_cast<unsigned>(v.house_learn ? v.house_learn->days : 0));
    for (int i = 0; i < g_n_flex; i++) p = jappend(p, "%s%d", i ? "," : "", g_flex_relay[i] ? 1 : 0);
    jappend(p, "]}");
    return g_json;
}

}  // extern "C"
