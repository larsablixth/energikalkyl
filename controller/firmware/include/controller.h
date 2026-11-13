#pragma once
// ── The controller: every decision the NORVI makes, in one portable module ──
//
// controller.cpp holds what used to be main.cpp's orchestration: the day
// (13:30 fetch of tomorrow, midnight swap, fetching today after a reboot),
// the safe state, look-ahead re-planning, learning the house, the go-e
// setpoint (planner request vs fuse guard cap), and the per-slot pipeline
// step; the fuse guard and surplus steps run through it as well.
//
// It has no FreeRTOS, Arduino, SD card or network code. Everything it needs
// from the outside world comes through ControllerHw: the inverter, the car
// charger, the meter, the relays, prices and weather, storage for what it
// learns, the clock, and log/display output.
//
//   NORVI (main.cpp):  ControllerHw = the real drivers, time()/millis(), the
//                      SD card; three FreeRTOS tasks call the three ticks.
//   Simulator / tests: ControllerHw = simulated devices and a simulated
//                      clock; a loop moves the clock and calls the ticks.
//
// So the simulator runs the controller itself, not a copy of it.
//
// Ticks (call each at its interval; each is one iteration of a task):
//   controller_scheduler_tick()  every SCHED_POLL_MS   (scheduler task)
//   controller_guard_tick()      every FUSE_GUARD_POLL_MS (fuse guard task)
//   controller_surplus_tick()    every SURPLUS_POLL_MS  (surplus task)
// On the NORVI the three run in different tasks: shared state is kept to
// single-word values and the go-e command sequence takes ControllerHw::lock.

#include <cstdint>
#include <ctime>
#include "pipeline.h"
#include "deye_modbus.h"
#include "goe_rest.h"
#include "tibber_pulse.h"
#include "fuse_guard.h"
#include "plan_state.h"
#include "house_learn.h"

/** Scheduler poll period: well below a 15-min slot, so slot boundaries are
 *  hit within SCHED_POLL_MS. */
constexpr uint32_t SCHED_POLL_MS = 15000;

/** Minimum spacing of safe-program attempts while Modbus is failing. */
constexpr uint32_t SAFE_RETRY_MS = 60000;

struct ControllerHw {
    // ── Clock ──
    time_t   (*now_utc)() = nullptr;     // UTC seconds (time(nullptr) on the NORVI)
    uint32_t (*now_ms)()  = nullptr;     // monotonic ms, wraps (millis())

    // ── Inverter (deye_modbus.h) ──
    bool (*deye_read_soc)(float* soc_pct)                                       = nullptr;
    bool (*deye_read_power_status)(DeyePowerStatus* out)                        = nullptr;
    bool (*deye_sample_power_status)(DeyePowerStatus* out)                      = nullptr;  // failures don't count
    bool (*deye_set_program_segments)(const ProgSegment* segs, int n, int grid_charge_a) = nullptr;
    bool (*deye_set_charge_windows)(const TouWindow* w, int n, int grid_charge_a)        = nullptr;
    bool (*deye_set_charge)(int start_min, int end_min, int target_soc)         = nullptr;
    bool (*deye_set_idle)()                                                     = nullptr;
    bool (*deye_apply_safe_program)()                                           = nullptr;
    bool (*deye_grid_charge_enabled)()                                          = nullptr;
    int  (*deye_consecutive_failures)()                                         = nullptr;
    void (*deye_invalidate_cache)()                                             = nullptr;

    // ── Car charger (goe_rest.h) ──
    bool (*goe_get_status)(GoeStatus* out) = nullptr;
    bool (*goe_set_amps)(int amps)         = nullptr;
    bool (*goe_stop_charging)()            = nullptr;
    bool (*goe_release_stop)()             = nullptr;

    // ── Prices, weather, meter ──
    int  (*fetch_prices)(int y, int m, int d, float* out, int max_slots, int* slot_min) = nullptr;
    // Outdoor temperature forecast °C per slot (SMHI on the NORVI); nullptr / false = none.
    bool (*forecast_temp_c)(const DaySlotClock* clk, int month, float* temp_c_out) = nullptr;
    // Per-phase meter reading for the fuse guard; true only for a validated reading.
    bool (*read_meter)(TibberPulseData* out) = nullptr;

    // ── Flex loads (relays / plugs) ──
    bool (*flex_set)(const FlexLoadConfig* cfg, int index, bool on) = nullptr;

    // ── Storage for what the controller learns (SD card); nullptr = not kept ──
    int  (*storage_read)(const char* name, uint8_t* buf, int max_len)        = nullptr;  // bytes, -1 = none
    bool (*storage_write)(const char* name, const uint8_t* buf, int len)     = nullptr;

    // ── Output ──
    void (*log_msg)(const char* level, const char* msg)                           = nullptr;
    void (*show_status)(const char* l1, const char* l2, const char* l3, const char* l4) = nullptr;
    void (*show_error)(const char* msg)                                           = nullptr;
    void (*delay_ms)(unsigned long ms)                                            = nullptr;  // pipeline retries
    void (*feed_watchdog)()                                                       = nullptr;

    // ── Optional lock around go-e command sequences (bus shared with the guard) ──
    bool (*lock)()   = nullptr;
    void (*unlock)() = nullptr;
};

struct ControllerConfig {
    const FlexLoadConfig* flex_loads = nullptr;   // copied; ≤ MAX_FLEX_LOADS
    int   n_flex_loads     = 0;
    float load_plan_factor = HOUSE_LOAD_PLAN_FACTOR;   // settings.txt
};

/** Everything the controller exposes for display, logging and tests. */
struct ControllerView {
    const PipelineDayContext* today    = nullptr;
    const PipelineDayContext* tomorrow = nullptr;
    bool today_valid        = false;
    bool tomorrow_valid     = false;
    bool safe_hold          = true;
    bool safe_confirmed     = false;
    bool boot_safe_ok       = false;
    bool safe_pending       = true;
    SafetyAction safe_reason = SAFETY_TIME_INVALID;
    bool lookahead_pending  = false;
    int  last_slot          = -1;
    int64_t plan_written_utc = 0;
    int64_t plan_expires_utc = 0;
    // go-e / fuse guard
    int  goe_planned_amps   = -1;
    int  goe_applied_amps   = 0;
    int  guard_goe_cap      = 0;     // -1 = none
    bool guard_bat_inhibit  = true;
    FuseGuardStatus guard;
    // house learning
    const HouseLearnState* house_learn = nullptr;
    // counters
    uint32_t last_scheduler_run_ms = 0;
    int  scheduler_ticks    = 0;
    int  guard_ticks        = 0;
    int  surplus_ticks      = 0;
};

/** Set up (call once, before any tick): hardware, flex loads, and what was
 *  learned before (read through storage_read). Also resets all state. */
void controller_init(const ControllerHw* hw, const ControllerConfig& cfg);

/** One attempt at the boot SAFE program (write + read back). Call until it
 *  returns true or the boot attempts run out; the scheduler keeps retrying. */
bool controller_boot_safe();

/** One iteration of each task. */
void controller_scheduler_tick();
void controller_guard_tick();
void controller_surplus_tick();

const ControllerView& controller_view();

/** The pipeline IO the controller built from ControllerHw (tests). */
const PipelineIO* controller_pipeline_io();
