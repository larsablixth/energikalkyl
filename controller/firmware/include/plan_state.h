#pragma once
// Pure decision logic for following the plan through the day (no hardware):
//   - which day's plan is active (swap tomorrow → today at local midnight)
//   - the 13:30 price-fetch retry state machine
//   - when to fall back to the Deye safe program
// main.cpp executes the decisions; the functions only decide (unit-tested).

#include <cstdint>
#include <ctime>
#include "time_local.h"

// ── Day rollover ─────────────────────────────────────────────────────────
enum RolloverAction {
    ROLL_KEEP = 0,      // today's plan is for today: keep following it
    ROLL_SWAP,          // the stored "tomorrow" plan is for today: activate it
    ROLL_NO_PLAN,       // no plan for today: safe program (no grid charging)
};

// today_plan / tomorrow_plan: dates the stored plans were computed FOR.
// A plan is never applied to any other date than its own.
RolloverAction plan_rollover_decide(bool today_valid, const LocalDate& today_plan,
                                    bool tomorrow_valid, const LocalDate& tomorrow_plan,
                                    const LocalDate& now);

// ── Price fetch retry ────────────────────────────────────────────────────
enum FetchAction {
    FETCH_IDLE = 0,     // nothing to do now
    FETCH_NOW,          // attempt the fetch now, then call fetch_retry_result()
    FETCH_GIVE_UP,      // deadline passed without success: log + safe program
                        // for the target day (returned once per day)
};

struct FetchRetryState {
    LocalDate day;               // local day the state belongs to (reset on change)
    bool succeeded  = false;
    bool gave_up    = false;
    int  attempts   = 0;
    int  next_min   = -1;        // local minute of day of the next attempt
};

struct FetchRetryConfig {
    int start_min;               // first attempt (e.g. 13:30 = 810)
    int interval_min;            // retry interval (15)
    int deadline_min;            // no attempt at/after this minute (23:00)
};

// now_min: local minute of day. Resets the state when `today` changes.
FetchAction fetch_retry_decide(FetchRetryState* st, const FetchRetryConfig& cfg,
                               const LocalDate& today, int now_min);
void fetch_retry_result(FetchRetryState* st, const FetchRetryConfig& cfg,
                        bool ok, int now_min);

// ── Safe-state decision ──────────────────────────────────────────────────
enum SafetyAction {
    SAFETY_OK = 0,
    SAFETY_TIME_INVALID,   // no valid time: refuse to plan
    SAFETY_MODBUS,         // repeated Modbus failures
    SAFETY_PLAN_STALE,     // grid-charge plan written > max_age ago
    SAFETY_PLAN_EXPIRED,   // grid-charge plan past its expiry (day over)
    SAFETY_NO_PLAN,        // no plan for today (set by the caller, not by
                           // safety_decide: see plan_rollover_decide)
};

struct SafetyInputs {
    bool    time_valid        = false;
    bool    grid_charge_programmed = false;  // last written program charges
    int64_t now_utc           = 0;
    int64_t plan_written_utc  = 0;           // 0 = never written
    int64_t plan_expires_utc  = 0;           // 0 = no expiry known
    int     modbus_failures   = 0;
    int     max_modbus_failures = 5;
    int64_t max_plan_age_s    = 26 * 3600;
};

SafetyAction safety_decide(const SafetyInputs& in);
const char* safety_action_name(SafetyAction a);

// ── Grid-charge write gate ───────────────────────────────────────────────
// "Safe program pending": set at boot and on every safety condition (need !=
// SAFETY_OK); cleared only once the condition is gone AND the boot safe
// program has been written + verified AND time is valid AND a plan for today
// exists. Otherwise the previous value is kept. Returns the new value.
bool safe_pending_next(bool pending, SafetyAction need, bool safe_program_verified,
                       bool time_valid, bool today_plan_valid);

// A grid-charge program (windows / segments / single window) may be written
// only while the fuse guard does not inhibit battery charging, no safe
// program is pending and the time is valid.
bool charge_write_permitted(bool guard_bat_inhibit, bool safe_pending, bool time_valid);

// Expiry instant for a plan written for local date d: end of that local day
// plus grace_s. Grid-charge windows are never allowed to outlive their day.
int64_t plan_expiry_utc(const LocalDate& d, int64_t grace_s);
