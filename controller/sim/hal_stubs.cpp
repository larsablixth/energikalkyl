// ── HAL stubs: C++ → JavaScript hooks (EM_JS) ───────────────────────────
//
// Each js_* function below is implemented in JavaScript and calls one method
// of the `Module.hal` object that sim-scheduler.js (UI) installs. The hal_*
// wrappers are what the rest of the binding layer uses (sim_hal.h).
//
// In a native build (wasm/native/emscripten/emscripten.h) EM_JS only
// declares js_* as extern "C"; wasm/native/driver.cpp implements them.
//
// This file also provides the few firmware link dependencies that would
// otherwise need ESP32 hardware drivers (logger, Deye live read, flex relay,
// FreeRTOS delay). None of them contains control logic.

#include <emscripten/emscripten.h>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cmath>

#include "sim_hal.h"
#include "logger.h"
#include "deye_modbus.h"
#include "flex_control.h"
#include "goe_rest.h"
#include <Arduino.h>

// ── JavaScript hooks ─────────────────────────────────────────────────────
// (Bodies are JavaScript. HEAP views are refreshed by Emscripten on memory
// growth; the hooks only touch them after calling into JS.)

EM_JS(double, js_now_utc, (), {
    var h = Module.hal;
    return (h && h.nowUtc) ? +h.nowUtc() : 0;
});

EM_JS(int, js_read_soc, (float* out), {
    var h = Module.hal;
    if (!h || !h.readSoc) return 0;
    var v = h.readSoc();
    if (v === null || v === undefined || !isFinite(v)) return 0;
    HEAPF32[out >> 2] = v;
    return 1;
});

EM_JS(int, js_fetch_prices, (int y, int m, int d, float* out, int max_slots, int* slot_min), {
    var h = Module.hal;
    if (!h || !h.fetchPrices) return 0;
    var r = h.fetchPrices(y, m, d);
    if (!r || !r.prices || !r.prices.length) return 0;
    var n = Math.min(r.prices.length, max_slots);
    for (var i = 0; i < n; i++) HEAPF32[(out >> 2) + i] = +r.prices[i] || 0;
    HEAP32[slot_min >> 2] = r.slotMin || 60;
    return n;
});

EM_JS(int, js_forecast, (int which, double day_start_utc, int slot_min, int n, int month, float* out), {
    var h = Module.hal;
    if (!h || !h.forecast) return 0;
    var kind = which === 0 ? "solar" : which === 1 ? "load" : "temp";
    var a = h.forecast(kind, day_start_utc, slot_min, n, month);
    if (!a || a.length < n) return 0;
    for (var i = 0; i < n; i++) {
        var v = +a[i];
        if (which === 2) {                  // °C: may be negative; NaN = missing
            HEAPF32[(out >> 2) + i] = (a[i] === null || isNaN(v)) ? NaN : v;
        } else {
            HEAPF32[(out >> 2) + i] = Math.max(0, v || 0);
        }
    }
    return 1;
});

EM_JS(int, js_write_program, (const uint16_t* regs, int n), {
    var h = Module.hal;
    if (!h || !h.writeProgram) return 0;
    var a = new Array(n);
    for (var i = 0; i < n; i++) a[i] = HEAPU16[(regs >> 1) + i];
    return h.writeProgram(a) ? 1 : 0;
});

EM_JS(int, js_read_live, (float* out), {
    var h = Module.hal;
    if (!h || !h.readLive) return 0;
    var r = h.readLive();
    if (!r) return 0;
    var b = out >> 2;
    HEAPF32[b] = r.gridW; HEAPF32[b + 1] = r.loadW; HEAPF32[b + 2] = r.pvW;
    HEAPF32[b + 3] = r.soc; HEAPF32[b + 4] = r.batW;
    return 1;
});

EM_JS(int, js_read_meter, (float* out), {
    var h = Module.hal;
    if (!h || !h.readMeter) return 0;
    var r = h.readMeter();
    if (!r) return 0;
    var b = out >> 2;
    HEAPF32[b] = r.l1; HEAPF32[b + 1] = r.l2; HEAPF32[b + 2] = r.l3; HEAPF32[b + 3] = r.powerW;
    return 1;
});

EM_JS(int, js_goe_status, (float* out), {
    var h = Module.hal;
    if (!h || !h.goeStatus) return 0;
    var r = h.goeStatus();
    if (!r) return 0;
    var b = out >> 2;
    HEAPF32[b] = r.connected ? 1 : 0; HEAPF32[b + 1] = r.amps; HEAPF32[b + 2] = r.soc;
    return 1;
});

EM_JS(int, js_goe_set_amps, (int amps), {
    var h = Module.hal;
    return (h && h.goeSetAmps && h.goeSetAmps(amps)) ? 1 : 0;
});

EM_JS(int, js_flex_set, (int index, int on), {
    var h = Module.hal;
    return (h && h.flexSet && h.flexSet(index, !!on)) ? 1 : 0;
});

EM_JS(void, js_log, (const char* level, const char* msg), {
    var h = Module.hal;
    if (h && h.log) h.log(UTF8ToString(level), UTF8ToString(msg));
});

EM_JS(void, js_display, (const char* l1, const char* l2, const char* l3, const char* l4), {
    var h = Module.hal;
    if (h && h.display) h.display(UTF8ToString(l1), UTF8ToString(l2), UTF8ToString(l3), UTF8ToString(l4));
});

// ── hal_* wrappers ───────────────────────────────────────────────────────

double hal_now_utc() { return js_now_utc(); }

uint32_t hal_now_ms() {
    const double t = js_now_utc();
    return static_cast<uint32_t>(std::fmod(t * 1000.0, 4294967296.0));
}

bool hal_read_soc(float* soc) { return js_read_soc(soc) != 0; }

int hal_fetch_prices(int y, int m, int d, float* out, int max_slots, int* slot_min) {
    return js_fetch_prices(y, m, d, out, max_slots, slot_min);
}

bool hal_forecast(int which, double day_start_utc, int slot_min, int n, int month, float* out) {
    return js_forecast(which, day_start_utc, slot_min, n, month, out) != 0;
}

bool hal_write_program(const uint16_t* regs) {
    return js_write_program(regs, HAL_PROGRAM_REGS) != 0;
}

bool hal_read_live(HalLive* out) {
    float b[5] = {};
    if (!js_read_live(b)) return false;
    out->grid_w = b[0]; out->load_w = b[1]; out->pv_w = b[2]; out->soc = b[3]; out->bat_w = b[4];
    return true;
}

bool hal_read_meter(HalMeter* out) {
    float b[4] = {};
    if (!js_read_meter(b)) return false;
    out->l1_a = b[0]; out->l2_a = b[1]; out->l3_a = b[2]; out->power_w = b[3];
    return true;
}

bool hal_goe_status(HalGoe* out) {
    float b[3] = {};
    if (!js_goe_status(b)) return false;
    out->connected = b[0] > 0.5f;
    out->amps = static_cast<int>(std::lround(b[1]));
    out->soc = b[2];
    return true;
}

bool hal_goe_set_amps(int amps) { return js_goe_set_amps(amps) != 0; }
bool hal_flex_set(int index, bool on) { return js_flex_set(index, on ? 1 : 0) != 0; }
void hal_log(const char* level, const char* msg) { js_log(level, msg); }
void hal_display(const char* l1, const char* l2, const char* l3, const char* l4) {
    js_display(l1 ? l1 : "", l2 ? l2 : "", l3 ? l3 : "", l4 ? l4 : "");
}

// ── Firmware link dependencies ─────────────────────────────────────────────

void logger_init(void) {}
void logger_log(const char* level, const char* msg) { hal_log(level, msg); }
void logger_log_schedule(const DaySchedule* sched, const int* ev_slots, int n_ev_slots) {
    (void)sched; (void)ev_slots; (void)n_ev_slots;
}

// The controller (firmware controller.cpp) reaches every device through
// ControllerHw, implemented in wasm/controller_hal.cpp — no driver symbols
// are needed here any more.
