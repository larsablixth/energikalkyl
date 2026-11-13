#pragma once

#include <cstdint>
#include "pipeline.h"
#include "tibber_pulse.h"
#include "homewizard_p1.h"
#include "easee_client.h"

// ── Fast Fuse Guard ──────────────────────────────────────────────────
// Runs every few seconds (not every 15 min like the scheduler).
// Reads per-phase current (HomeWizard P1 / Tibber Pulse) and sheds
// NORVI-controlled loads if any phase approaches the DIAZED fuse limit.
//
// Tibber controls the Easee charger but reacts slowly. The NORVI must
// be the fast-acting fuse protector for its own loads (go-e, battery).
//
// Limit: SUSTAINED = nominal In (25 A), only ever reduced by temperature
// derating. No IEC 60269 Inf headroom. Thresholds (config.h, % of limit):
//   level 1  ≥ FUSE_GOE_REDUCE_PCT (85%)  reduce go-e amps (min GOE_MIN_AMPS)
//   level 2  ≥ FUSE_BAT_PAUSE_PCT  (92%)  + pause battery grid-charge
//   level 3  ≥ FUSE_HP_SHED_PCT    (98%)  + pause go-e, shed pool heat pump
//   hard     ≥ FUSE_HARD_TRIP_PCT (110%)  single reading → level 3 at once
// Levels 1-3 need FUSE_ESCALATE_CONFIRM_READINGS consecutive readings.
// Restore: one level down after FUSE_RESTORE_HOLD_MS continuously below
// FUSE_RESTORE_PCT (75%); the timer restarts after every step.
// Meter stale (> FUSE_METER_STALE_MS without a valid reading, or none since
// boot): safe state = go-e ≤ GOE_MIN_AMPS + battery grid-charge paused.
//
// The Easee is never touched — Tibber owns it.
//
// Design: fuse_guard_evaluate() is a pure decision function (state + input
// in, decision out; no I/O, no clock, no globals). The FreeRTOS task reads
// the meter and the load states, calls evaluate(), and actuates through an
// injected FuseGuardIO, so the decision logic is unit-testable natively.

constexpr int FUSE_GUARD_POLL_MS = 5000;    // poll meter every 5 seconds

constexpr int FUSE_SHED_NONE = 0;
constexpr int FUSE_SHED_GOE  = 1;   // go-e reduced
constexpr int FUSE_SHED_BAT  = 2;   // + battery grid-charge paused
constexpr int FUSE_SHED_HP   = 3;   // + go-e paused, pool HP off
constexpr int FUSE_SHED_MAX  = FUSE_SHED_HP;

// Persistent guard state. Zero-initialise via fuse_guard_state_init().
struct FuseGuardState {
    float    fuse_limit_a      = 0.0f;   // sustained limit (≤ nominal)
    int      shed_level        = 0;      // FUSE_SHED_*
    int      goe_limit_a       = 0;      // go-e cap while shed_level ≥ 1 (0 = paused)
    bool     have_good_reading = false;  // any valid reading since boot
    uint32_t last_good_ms      = 0;      // time of last valid reading
    bool     below_restore     = false;  // currently in a below-restore streak
    uint32_t below_since_ms    = 0;      // start of that streak
    int      recent_levels[4]  = {};     // last N reading levels (confirmation)
    int      n_recent          = 0;
    // Deye write rate limiting
    bool     bat_cmd_paused    = false;  // last battery command we sent
    bool     bat_cmd_valid     = false;  // we have sent a battery command
    uint32_t last_bat_cmd_ms   = 0;
    // Actuation bookkeeping (fuse_guard_step only)
    int      goe_cap_applied   = -1;     // cap last written to go-e, -1 = none
};

// One evaluation input. `meter` may be null; `meter_valid` must be false if
// the reading failed validation (see fuse_guard_reading_valid()).
struct FuseGuardInput {
    const TibberPulseData* meter = nullptr;
    bool     meter_valid           = false;
    uint32_t now_ms                = 0;      // millis(); wrap-safe arithmetic
    int      goe_amps              = 0;      // go-e current setpoint (0 = paused)
    bool     battery_grid_charging = false;  // Deye TOU grid-charge active
    bool     hp_running            = false;  // pool HP on
};

enum FuseBatAction {
    FUSE_BAT_NONE   = 0,
    FUSE_BAT_PAUSE  = 1,   // pause grid-charge now (never rate-limited)
    FUSE_BAT_RESUME = 2,   // guard releases the battery (rate-limited)
};

typedef struct {
    float max_phase_a;        // highest phase current from this reading (0 if none)
    float fuse_limit_a;       // sustained limit used (≤ nominal In)
    float utilization_pct;    // max_phase / fuse_limit × 100
    bool  meter_stale;        // no valid reading for > FUSE_METER_STALE_MS
    bool  hard_trip;          // this reading crossed FUSE_HARD_TRIP_PCT
    bool  goe_reduced;        // go-e must be capped at goe_limit_a
    int   goe_limit_a;        // cap for go-e (0 = paused); valid if goe_reduced
    bool  bat_paused;         // battery grid-charge must be paused
    bool  hp_shed;            // pool heat pump must be off
    int   shed_level;         // 0=none, 1=goe reduced, 2=bat paused, 3=hp shed
    int   bat_action;         // FuseBatAction: Deye write to perform this cycle
} FuseGuardStatus;

// Actuation callbacks injected into the task (like PipelineIO).
struct FuseGuardIO {
    // Meter: fill *out and return true only for a VALIDATED reading.
    bool (*read_meter)(TibberPulseData* out)              = nullptr;
    // Current load state (best effort, called every cycle).
    int  (*get_goe_amps)()                                = nullptr;  // 0 = paused
    bool (*battery_grid_charging)()                       = nullptr;
    bool (*hp_running)()                                  = nullptr;
    // Actuators. set_goe_limit(0) = pause, otherwise cap in amps.
    bool (*set_goe_limit)(int amps)                       = nullptr;
    bool (*clear_goe_limit)()                             = nullptr;
    bool (*pause_battery)()                               = nullptr;
    bool (*resume_battery)()                              = nullptr;
    bool (*set_hp)(bool on)                               = nullptr;
    // Publish the decision for other tasks (scheduler/surplus) to respect.
    void (*publish)(const FuseGuardStatus* st)            = nullptr;
    void (*log_msg)(const char* level, const char* msg)   = nullptr;
    uint32_t (*now_ms)()                                  = nullptr;
    void (*delay_ms)(unsigned long ms)                    = nullptr;
    void (*feed_watchdog)()                               = nullptr;
};

// Initialise guard state with the nominal (sustained) fuse limit.
void fuse_guard_state_init(FuseGuardState* st);

// Update the sustained limit from a fuse/cabinet temperature (°C).
// Only ever lowers the limit below nominal (see fuse_effective_amps_temp).
void fuse_guard_set_temperature(FuseGuardState* st, float temp_celsius);

// Validate a per-phase reading: finite, |I| ≤ FUSE_METER_MAX_PLAUSIBLE_A.
// Normalises currents to absolute values (export shows as negative on some
// meters, but heats the fuse just the same) and recomputes max_phase_a.
bool fuse_guard_reading_valid(TibberPulseData* reading);

// Pure decision function. Mutates only *st. No I/O.
FuseGuardStatus fuse_guard_evaluate(FuseGuardState* st, const FuseGuardInput* in);

// One task iteration: read → evaluate → actuate (uses only io callbacks).
// Exposed so the whole loop is testable with mock IO.
FuseGuardStatus fuse_guard_step(FuseGuardState* st, const FuseGuardIO* io);

// FreeRTOS task. param must point to a FuseGuardIO that outlives the task.
void fuse_guard_task(void* param);
