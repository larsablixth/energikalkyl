#pragma once

#include <ctime>
#include "pipeline.h"
#include "deye_modbus.h"
#include "goe_rest.h"

// Per-load surplus activation state (persists between evaluations)
typedef struct {
    bool  active;
    int   surplus_count;    // consecutive surplus polls
    int   deficit_count;    // consecutive deficit polls
    float today_kwh;        // energy consumed today (reset at midnight)
    int   last_day;         // day-of-month for daily reset
} FlexSurplusState;

// Evaluate one flex load against current surplus.
// Returns true if load should be active, false if inactive.
// Updates state counters for hysteresis (2 consecutive polls before toggle).
// Mutates *surplus_kw — reduces it when a load activates.
// If total_cost_sek < 0 (TOTAL buying cost: spot × VAT + grid fee + energy tax), activates regardless of surplus
// (cheaper to consume than not — negative total electricity cost).
// Pure function: no hardware access, no logging.
bool surplus_eval_load(const FlexLoadConfig* config,
                       const void* sched_result,  // reserved (unused), pass NULL
                       FlexSurplusState* state,
                       float* surplus_kw,
                       int current_hour, int current_month,
                       float total_cost_sek);

// Solar surplus in kW (> 0 = available for flex loads) from the Deye grid
// CT reading (grid_power_w, + import / − export). ct_sees_goe
// (DEYE_CT_SEES_GOE): the CT already measures the go-e draw, so the EV is
// inside grid_power_w and is NOT subtracted again (it naturally has priority
// over flex loads). Otherwise the go-e draw (goe_power_w) is not on the CT
// and is subtracted here.
float surplus_from_deye_grid(float grid_power_w, float goe_power_w, bool ct_sees_goe);

// Initialize the surplus task with flex load configs and a shared pipeline result.
// The surplus task reads the pipeline result to know scheduled windows.
void surplus_task_init(FlexLoadConfig* configs, int n_configs,
                       const PipelineResult* shared_result);

// Store TODAY's total cost per slot (spot + grid fee, SEK/kWh). Called by
// the scheduler when a day becomes today (midnight swap). day_start_utc is
// the UTC instant of slot 0 (local midnight); the current slot is computed
// from UTC so DST days (92/100 slots) map correctly. slot_count 0 = clear.
void surplus_set_today_prices(const float* total_costs, int slot_count,
                              int slot_duration_min, int64_t day_start_utc);

// Hardware the surplus poll uses (set by the controller, controller.h).
struct SurplusIO {
    bool (*read_power)(DeyePowerStatus* out)                       = nullptr;  // Deye live data
    bool (*goe_status)(GoeStatus* out)                             = nullptr;  // only if !DEYE_CT_SEES_GOE
    bool (*flex_set)(const FlexLoadConfig* cfg, int index, bool on) = nullptr;  // relay / plug
    void (*log_msg)(const char* level, const char* msg)            = nullptr;
};
void surplus_set_io(const SurplusIO* io);

// One surplus poll (every SURPLUS_POLL_MS): read the Deye, work out the
// solar surplus and switch flex loads on/off with hysteresis. now_utc =
// current time (local hour/month for the loads' seasons, today's slot for
// the negative-price override). Does nothing without loads or io.
void surplus_poll(time_t now_utc);

// ── Fuse guard hooks ─────────────────────────────────────────────────
// While inhibited (fuse guard level 3), no flex load may switch ON; loads
// found ON are switched OFF on the next poll.
void surplus_set_inhibit(bool inhibit);

// True if any flex load is currently ON (as commanded by this task).
bool surplus_any_load_active(void);

// Switch every active flex load OFF immediately (called by the fuse guard).
// Returns true if all OFF commands succeeded.
bool surplus_shed_all(void);
