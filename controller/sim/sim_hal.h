#pragma once
// ── Simulator HAL: the C++ side of the "JS world" bridge ────────────────
//
// The firmware talks to hardware through PipelineIO / FuseGuardIO function
// pointers (pipeline.h, fuse_guard.h). In the simulator those callbacks end
// up here, and every hal_* function calls ONE JavaScript hook on
// `Module.hal` (wasm/hal_stubs.cpp, EM_JS). The JS side (sim-scheduler.js)
// answers from the simulated hardware (sim-hardware.js).
//
// Native builds (wasm/native/driver.cpp) implement the same js_* hooks in
// C++, so the identical binding layer also runs on the host.
//
// Units: W, A, %, SEK/kWh, kWh; times are UTC seconds (sim clock).

#include <cstdint>

struct HalLive {            // Deye live data (what the inverter reports)
    float grid_w  = 0.0f;   // + import, − export (Deye CT, whole house incl. EV)
    float load_w  = 0.0f;   // house load seen by the Deye
    float pv_w    = 0.0f;
    float soc     = 0.0f;   // %
    float bat_w   = 0.0f;   // + discharge, − charge (Deye sign)
};

struct HalMeter {           // HAN meter (HomeWizard P1) per-phase reading
    float l1_a = 0.0f, l2_a = 0.0f, l3_a = 0.0f;
    float power_w = 0.0f;
};

struct HalGoe {
    bool  connected = false;
    int   amps      = 0;     // current setpoint, 0 = paused
    float soc       = -1.0f;
};

double hal_now_utc();                       // sim clock (UTC seconds)
uint32_t hal_now_ms();                      // sim clock as millis() (wraps)
bool hal_read_soc(float* soc);
int  hal_fetch_prices(int y, int m, int d, float* out, int max_slots, int* slot_min);
// which: 0 = solar, 1 = house load (kWh per slot), 2 = outdoor temperature
// (°C per slot; NaN = missing) of the day described by (day_start_utc,
// slot_min, n). false = no forecast (firmware default model). The controller
// (firmware controller.cpp, via wasm/controller_hal.cpp) asks only for 2.
bool hal_forecast(int which, double day_start_utc, int slot_min, int n, int month, float* out);
// Full Deye program register image, see deye_program.h DeyeProgram:
//   regs[0..5] time HHMM, [6..11] power W, [12..17] SOC %, [18..23] charge
//   bits, [24] TOU enable (146), [25] grid charge enable (130), [26] grid
//   charge current A (128). Returns false if the "Modbus write" failed.
constexpr int HAL_PROGRAM_REGS = 27;
bool hal_write_program(const uint16_t* regs);
bool hal_read_live(HalLive* out);
bool hal_read_meter(HalMeter* out);
bool hal_goe_status(HalGoe* out);
bool hal_goe_set_amps(int amps);            // 0 = pause (frc=1)
bool hal_flex_set(int index, bool on);
void hal_log(const char* level, const char* msg);
void hal_display(const char* l1, const char* l2, const char* l3, const char* l4);
