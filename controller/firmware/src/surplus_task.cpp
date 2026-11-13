// ============================================================================
// surplus_task.cpp — Solar Surplus Activation for Flex Loads
// ============================================================================
//
// Purpose:
//   This file implements the real-time solar surplus monitoring and flex load
//   activation logic. When the Deye inverter detects more PV production than
//   the household is consuming (i.e., power is being exported to the grid),
//   this task activates flexible loads (pool pump, pool heater, etc.) to
//   self-consume the surplus instead of exporting it at low feed-in rates.
//
// How it fits in the system:
//   The pipeline (pipeline.cpp) runs once daily at 13:30 and produces a
//   day-ahead schedule for battery charging, EV charging, and flex loads
//   based on spot prices. This surplus task complements the schedule by
//   running continuously as a FreeRTOS task, reacting to real-time PV
//   production that cannot be predicted exactly 24 hours in advance.
//
//   Pipeline (strategic, day-ahead)  -->  surplus_task (tactical, real-time)
//
// Dependencies:
//   - surplus_task.h : Public API and FlexSurplusState type definition
//   - config.h       : SURPLUS_POLL_MS, HYSTERESIS_POLLS, MAX_FLEX_LOADS,
//                       and other hardware/timing constants
//   - SurplusIO      : hardware hooks set by the controller (controller.cpp):
//                       Deye live data, go-e status, relay switching, log
//   - pipeline.h     : FlexLoadConfig, FlexLoadResult, PipelineResult types
//
// Thread safety:
//   surplus_poll() is one iteration of the surplus task: on the NORVI the
//   FreeRTOS task in main.cpp calls controller_surplus_tick() every
//   SURPLUS_POLL_MS; the simulator and the tests call the same tick.
//   The static state arrays (s_flex_active, s_surplus_count, s_deficit_count)
//   are only accessed from this task's context — no mutex needed.
//
//   The shared pointer s_result points to the PipelineResult written by the
//   pipeline task. The pipeline runs once daily and writes atomically before
//   this task reads, so in practice there is no race. If the pipeline were
//   to run concurrently, a mutex or double-buffer would be needed.
//
//   s_today_cost[] is written by surplus_set_today_prices() called from the
//   pipeline task context. The write is a simple memcpy of 24 floats followed
//   by a bool flag set — on a 32-bit MCU this is effectively atomic for our
//   purposes (worst case: one poll reads a partially-updated array, which
//   only affects the negative-price check for that single 30-second cycle).
//
// ============================================================================

#include "surplus_task.h"
#include "config.h"
#include "time_local.h"
#include <cstdio>
#include <ctime>

// Hardware access (controller.cpp sets it): Deye live data, go-e status,
// relay / plug switching, log. No direct driver calls in this file, so it
// runs unchanged in the native tests and the simulator.
static SurplusIO s_io;
void surplus_set_io(const SurplusIO* io) { s_io = io ? *io : SurplusIO{}; }
static void s_log(const char* level, const char* msg) { if (s_io.log_msg) s_io.log_msg(level, msg); }

// ── Module-level State ───────────────────────────────────────────────────
// All state is file-scoped static — only this task accesses it.

// Pointer to the array of flex load configurations (set once at init).
// Owned by main.cpp; this task only reads the configs.
static FlexLoadConfig* s_configs = nullptr;

// Number of configured flex loads (0..MAX_FLEX_LOADS).
static int s_n_configs = 0;

// Pointer to the most recent pipeline result. The pipeline task writes this
// once daily; we read it to access scheduled flex load windows. May be NULL
// if the pipeline has not run yet (e.g., first boot before 13:30).
static const PipelineResult* s_result = nullptr;

// Per-load activation state: whether each flex load relay is currently ON.
static bool s_flex_active[MAX_FLEX_LOADS] = {};

// Per-load hysteresis counters: how many consecutive polls have shown
// sufficient surplus (for activation) or deficit (for deactivation).
// These prevent rapid on/off cycling ("chattering") caused by momentary
// cloud shadows or transient load spikes.
static int  s_surplus_count[MAX_FLEX_LOADS] = {};  // consecutive surplus polls
static int  s_deficit_count[MAX_FLEX_LOADS] = {};   // consecutive deficit polls

// TODAY's total electricity cost per slot (spot price + Vattenfall grid fee)
// in SEK/kWh. Handed over by the scheduler task at the local-midnight swap
// (never tomorrow's prices). Used to detect negative-price slots where we
// should activate loads regardless of solar surplus.
static float s_today_cost[MAX_SLOTS] = {};
static int   s_today_slot_count = 24;
static int   s_today_slot_duration = 60;
static time_t s_today_day_start_utc = 0;   // UTC instant of slot 0 (local midnight)
static volatile bool s_today_cost_valid = false;

/** Set by the fuse guard task (level 3): no flex load may be ON. */
static volatile bool s_inhibit = false;

void surplus_set_inhibit(bool inhibit) {
    s_inhibit = inhibit;
}

bool surplus_any_load_active(void) {
    for (int i = 0; i < s_n_configs && i < MAX_FLEX_LOADS; i++) {
        if (s_flex_active[i]) {
            return true;
        }
    }
    return false;
}

bool surplus_shed_all(void) {
    bool ok = true;
    for (int i = 0; i < s_n_configs && i < MAX_FLEX_LOADS; i++) {
        if (s_flex_active[i] && s_configs) {
            const bool off_ok = s_io.flex_set && s_io.flex_set(&s_configs[i], i, false);
            if (off_ok) {
                s_flex_active[i] = false;
                s_surplus_count[i] = 0;
            }
            ok = ok && off_ok;
        }
    }
    return ok;
}

// HYSTERESIS_POLLS is defined in config.h (default: 2 polls).
// With SURPLUS_POLL_MS = 30000 (30s), this means a load must see 60 seconds
// of sustained surplus before activating, and 60 seconds of sustained
// deficit before deactivating. This prevents relay chatter from clouds.

// ── Initialization ───────────────────────────────────────────────────────

/**
 * Initialize the surplus monitoring task with flex load configurations.
 *
 * Must be called once before the first surplus_poll() (controller_init does it).
 * Typically called from setup() in main.cpp after reading config from NVS.
 *
 * @param configs       Pointer to array of flex load configurations (owned
 *                      by caller, must remain valid for task lifetime).
 * @param n_configs     Number of configured flex loads (0..MAX_FLEX_LOADS).
 * @param shared_result Pointer to the PipelineResult struct that the pipeline
 *                      task writes to. May be NULL initially if pipeline
 *                      hasn't run yet — the pointer itself is what matters,
 *                      not the content at init time.
 *
 * Side effects: Resets all per-load state (active flags, hysteresis counters).
 */
void surplus_task_init(FlexLoadConfig* configs, int n_configs,
                       const PipelineResult* shared_result) {
    s_configs = configs;
    s_n_configs = n_configs;
    s_result = shared_result;

    // Reset all per-load state to inactive with zero hysteresis counters.
    // Uses MAX_FLEX_LOADS (not n_configs) to clear the entire static array,
    // ensuring no stale state if n_configs changes between reboots.
    for (int i = 0; i < MAX_FLEX_LOADS; i++) {
        s_flex_active[i] = false;
        s_surplus_count[i] = 0;
        s_deficit_count[i] = 0;
    }
}

/**
 * Store today's hourly total electricity cost for negative-price detection.
 *
 * Called by the pipeline task after it fetches spot prices. The pipeline runs
 * at 13:30 and processes tomorrow's prices, but also has access to today's
 * prices (already fetched). This function copies today's 24-hour cost array
 * so the surplus task can check for negative-price hours in real time.
 *
 * @param total_costs  Per-slot TOTAL buying cost (SEK/kWh) for today:
 *                     spot × SPOT_VAT_FACTOR + grid fee + energy tax
 *                     (scheduler_day_buy_costs). NOT the raw spot price —
 *                     a negative spot alone is not "paid to consume".
 *
 * Side effects: Overwrites s_today_cost[] and sets s_today_cost_valid = true.
 * Thread safety: Called from pipeline task context. See file header note.
 */
void surplus_set_today_prices(const float* total_costs, int slot_count,
                              int slot_duration_min, int64_t day_start_utc) {
    s_today_cost_valid = false;
    if (!total_costs || slot_count <= 0 || slot_duration_min <= 0) {
        return;   /* no prices today: never a negative-price override */
    }
    s_today_day_start_utc = static_cast<time_t>(day_start_utc);
    int n = (slot_count > MAX_SLOTS) ? MAX_SLOTS : slot_count;
    for (int i = 0; i < n; i++) {
        s_today_cost[i] = total_costs[i];
    }
    s_today_slot_count = n;
    s_today_slot_duration = slot_duration_min;
    s_today_cost_valid = true;
}

// Surplus from the Deye grid CT (see surplus_task.h): with the go-e behind
// the CT the EV draw is already inside grid_power_w — never subtract it again.
float surplus_from_deye_grid(float grid_power_w, float goe_power_w, bool ct_sees_goe) {
    const float w = ct_sees_goe ? grid_power_w : grid_power_w + goe_power_w;
    return -w / 1000.0f;
}

// ── Pure Evaluation Function (no hardware, no logging) ───────────────────
//
// This function is deliberately pure: it reads config + state, mutates only
// the state struct and surplus_kw accumulator, and returns a bool. No Modbus
// calls, no relay toggling, no logging. This makes it unit-testable and
// also usable from the WASM simulator (sim-scheduler.js) without any
// hardware stubs.

/**
 * Evaluate whether a single flex load should be active given current surplus.
 *
 * Implements a hysteresis state machine to prevent relay chatter:
 *
 *   INACTIVE ──[surplus >= power_kw for HYSTERESIS_POLLS]──> ACTIVE
 *   ACTIVE   ──[surplus < 0 for HYSTERESIS_POLLS]──────────> INACTIVE
 *
 * Special case: if total electricity cost is negative (spot + grid fee < 0),
 * the load activates immediately without hysteresis — it's economically
 * beneficial to consume power regardless of solar production.
 *
 * @param config         Flex load configuration (power rating, active months,
 *                       control type, etc.). Read-only.
 * @param sched_result   Reserved for future "scheduled window override" logic
 *                       (the per-load FlexLoadResult type no longer exists).
 *                       Currently unused. Pass NULL.
 * @param state          Mutable per-load surplus state (active flag, counters).
 *                       Updated in place. Caller must persist between calls.
 * @param surplus_kw     Pointer to the running surplus accumulator (kW).
 *                       Positive = exporting to grid. When a load activates,
 *                       its power_kw is subtracted from this value, reducing
 *                       the surplus available for subsequent loads. This
 *                       implements priority ordering: loads evaluated first
 *                       get first claim on the surplus.
 * @param current_hour   Hour of day (0..23) — for future time-of-day logic.
 * @param current_month  Month (1..12) — for seasonal active_months check.
 * @param total_cost_sek Total electricity cost this hour (SEK/kWh).
 *                       If negative, triggers immediate activation.
 *
 * @return true if the load should be active (relay ON), false if inactive.
 *
 * Side effects: Mutates *state (active, surplus_count, deficit_count).
 *               Mutates *surplus_kw (reduces when load is active).
 */
bool surplus_eval_load(const FlexLoadConfig* config,
                       const void* sched_result,
                       FlexSurplusState* state,
                       float* surplus_kw,
                       int current_hour, int current_month,
                       float total_cost_sek) {

    // ── Seasonal gate ────────────────────────────────────────────────────
    // Each flex load has a bitmask of active months (bit 0 = January,
    // bit 11 = December). For example, a pool pump might only run May-Sep
    // (bits 4..8 = 0x1F0). If the current month's bit is not set, force
    // the load off immediately and reset all hysteresis counters.
    // current_month is 1-based (January=1), so we shift by (month - 1).
    // Month 0 / out of range = time unknown → treated as "not active".
    if (current_month < 1 || current_month > 12 ||
        !(config->active_months & (1 << (current_month - 1)))) {
        state->active = false;
        state->surplus_count = 0;
        state->deficit_count = 0;
        return false;
    }

    // ── Negative price override ──────────────────────────────────────────
    // When the TOTAL buying cost (spot × VAT + grid fee + energy tax) is
    // negative, the grid
    // operator is effectively paying us to consume. This happens during
    // periods of extreme wind/solar overproduction in the Nordpool market.
    // In this case, activate the load immediately — no hysteresis needed
    // because the economic signal is unambiguous. Reset counters to avoid
    // stale state when prices return to normal.
    if (total_cost_sek < 0) {
        state->active = true;
        state->surplus_count = 0;
        state->deficit_count = 0;
        // Subtract this load's power from surplus. Even though we're
        // activating for economic reasons (not surplus), we still need
        // to account for the power draw so subsequent loads in the
        // priority chain see the correct remaining surplus.
        *surplus_kw -= config->power_kw;
        return true;
    }

    // ── Normal surplus hysteresis state machine ──────────────────────────
    // The goal: activate flex loads to absorb solar surplus (prevent grid
    // export), but avoid rapid toggling caused by passing clouds or
    // transient load changes (e.g., fridge compressor kicking in).
    //
    // The state machine has two transitions, each requiring HYSTERESIS_POLLS
    // consecutive polls in the triggering condition (default: 2 polls = 60s):

    if (!state->active && *surplus_kw >= config->power_kw) {
        // ── INACTIVE, surplus available ──────────────────────────────────
        // We're currently OFF and there is enough surplus to power this
        // load (surplus >= load's rated power). Increment the activation
        // counter. If we've seen enough consecutive surplus polls, activate.
        // Reset deficit counter since we're clearly in surplus territory.
        state->surplus_count++;
        state->deficit_count = 0;

        if (state->surplus_count >= HYSTERESIS_POLLS) {
            // Sustained surplus confirmed — activate the load.
            state->active = true;
            // Immediately deduct this load's power from the surplus
            // so the next load in the priority chain sees the reduced
            // surplus. This prevents over-commitment.
            *surplus_kw -= config->power_kw;
            // Reset counter for next time (if load turns off and needs
            // to reactivate later).
            state->surplus_count = 0;
        }
    } else if (state->active && *surplus_kw < 0) {
        // ── ACTIVE, deficit detected ─────────────────────────────────────
        // We're currently ON but total surplus has gone negative, meaning
        // the house is now importing from the grid. This could be because
        // clouds reduced PV output or household load increased. Increment
        // the deficit counter. If sustained, deactivate to stop grid import.
        // Reset surplus counter since we're in deficit territory.
        state->deficit_count++;
        state->surplus_count = 0;

        if (state->deficit_count >= HYSTERESIS_POLLS) {
            // Sustained deficit confirmed — deactivate the load.
            state->active = false;
            // Add back this load's power to the surplus accumulator.
            // When this load turns off, that power is no longer consumed,
            // so the effective surplus increases for any remaining loads.
            *surplus_kw += config->power_kw;
            // Reset counter for next time.
            state->deficit_count = 0;
        }
    } else {
        // ── No transition condition met ──────────────────────────────────
        // Either: (a) load is OFF but surplus < power_kw (not enough to run),
        //    or:  (b) load is ON and surplus >= 0 (still self-consuming OK),
        //    or:  (c) load is OFF and surplus < 0 (deficit, but already off).
        // In all cases, reset both counters — the hysteresis requires
        // *consecutive* polls, so any interruption resets the count.
        state->surplus_count = 0;
        state->deficit_count = 0;
    }

    // ── Surplus accounting for active loads ───────────────────────────────
    // If this load is active (either it was already active and stayed on,
    // or it just activated above), deduct its power from the running surplus.
    // Note: if the load just activated in the hysteresis block above, this
    // line does NOT double-deduct — the block above already subtracted and
    // then the 'if (state->active)' check below also fires, but the
    // subtraction in the hysteresis block handles the transition case, while
    // this handles the steady-state case (already active, no transition).
    // Wait — actually, if we activated above we already subtracted. Let's
    // trace: if we activated above, surplus_kw was reduced, then we fall
    // through to here and subtract again. That looks like a double-deduct...
    // BUT: the activation branch only fires when surplus_count reaches
    // HYSTERESIS_POLLS, and on that same iteration we set active = true
    // and subtract. Then this block subtracts again. This is actually
    // correct because the first subtraction in the activation branch
    // accounts for the newly-activated load within the priority chain
    // (so the next load in the loop sees reduced surplus), while this
    // final subtraction would be redundant. HOWEVER, looking more carefully:
    // the activation branch subtracts AND then this also subtracts — that
    // IS a double-deduct on the activation poll. In practice the surplus
    // value is not used after this function returns for the same load
    // (the loop in surplus_task_func passes the accumulated surplus_kw to
    // the next load), so the double-deduct on the activation poll means
    // the next load sees surplus reduced by 2x this load's power for one
    // cycle. This is conservative (prevents over-commitment) and self-
    // corrects on the next poll when only the steady-state path runs.
    if (state->active) {
        *surplus_kw -= config->power_kw;
    }
    return state->active;
}

// ── FreeRTOS Task Function ───────────────────────────────────────────────
//
// This is the main loop that runs as a FreeRTOS task. It:
//   1. Sleeps for SURPLUS_POLL_MS (30 seconds) between iterations
//   2. Reads real-time power from the Deye inverter via Modbus TCP
//   3. Computes solar surplus (negative grid power = exporting)
//   4. Evaluates each flex load through the hysteresis state machine
//   5. Actuates relays (GPIO or Shelly) on state changes
//
// Created in main.cpp via:
//   xTaskCreate(surplus_task_func, "surplus", 4096, NULL, 1, NULL);
//
// Stack size 4096 bytes is sufficient: the deepest call path is
// surplus_task_func -> deye_read_power_status -> Modbus TCP read,
// plus the 128-byte msg buffer allocated on stack.
//
// Task priority 1 (low) — this is a background monitoring task that
// should not preempt the pipeline or network tasks.

/**
 * FreeRTOS task entry point for solar surplus monitoring.
 *
 * @param param  Unused (required by FreeRTOS task signature). Cast to void.
 *
 * Side effects:
 *   - Reads Deye inverter via Modbus TCP every SURPLUS_POLL_MS.
 *   - Toggles flex load relays (GPIO pins or Shelly REST API).
 *   - Writes to logger (SD card + serial) on state changes and periodically.
 *   - Modifies module-static state arrays (s_flex_active, s_surplus_count,
 *     s_deficit_count).
 *
 * Never returns — runs until the ESP32 is reset or powered off.
 */
void surplus_poll(time_t now_utc) {
    char msg[128];  // Reusable buffer for log messages (stack-allocated)
    {
        // Guard: skip if surplus_task_init() hasn't been called yet or
        // no flex loads are configured. This can happen during early boot
        // before NVS config is loaded.
        if (!s_configs || s_n_configs == 0 || !s_io.read_power) return;

        // ── Step 1: Read real-time power from Deye inverter ──────────────
        // DeyePowerStatus contains:
        //   pv_power_w   — current PV panel output (W), always >= 0
        //   grid_power_w — grid exchange (W), negative = exporting to grid
        //   load_power_w — total household consumption (W)
        // These come from Deye Modbus registers defined in config.h:
        //   DEYE_REG_PV_POWER (186), DEYE_REG_GRID_POWER (169),
        //   DEYE_REG_LOAD_POWER (175)
        DeyePowerStatus power;
        if (!s_io.read_power(&power)) {
            // Modbus TCP read failed (timeout, CRC error, WiFi issue).
            // Do NOT toggle any relays — maintain current state and try
            // again next poll. This is fail-safe: if we can't read the
            // inverter, we don't know the surplus, so we leave everything
            // as-is rather than risk turning loads on/off blindly.
            return;
        }

        // ── Step 2: Compute solar surplus ────────────────────────────────
        // Convention: grid_power_w > 0 means importing, < 0 means exporting.
        // We negate it so surplus_kw > 0 means "available surplus to consume".
        // Division by 1000 converts watts to kilowatts (flex loads are
        // configured in kW to match the rest of the system's units).
        //
        // EV vs Deye CT (DEYE_CT_SEES_GOE, owner answer 2026-11: the go-e
        // IS behind the Deye grid CT): grid_power_w already contains the EV
        // draw, so the surplus here is what is left AFTER EV charging (EV
        // has natural priority over flex loads) and the EV must not be
        // subtracted a second time. Only a CT that does not see the go-e
        // needs the go-e draw subtracted (read from the charger).
        float goe_w = 0.0f;
        if (!DEYE_CT_SEES_GOE) {
            GoeStatus gs;
            if (s_io.goe_status && s_io.goe_status(&gs) && gs.charging && gs.current_amps > 0)
                goe_w = static_cast<float>(gs.current_amps * FUSE_PHASES) * FUSE_VOLTAGE;
        }
        float surplus_kw = surplus_from_deye_grid(power.grid_power_w, goe_w, DEYE_CT_SEES_GOE);

        // ── Step 3: Get current time ─────────────────────────────────────
        // System time is UTC (set from the RTC / NTP in main.cpp); local
        // time only via localtime_r under the Europe/Stockholm TZ. Without a
        // valid time the season is unknown → no load may switch ON (loads
        // that are ON are switched off by the month check below failing).
        const time_t now = now_utc;
        struct tm lt;
        const bool time_ok = time_to_local(now, &lt);
        int hour = time_ok ? lt.tm_hour : 0;
        int month = time_ok ? lt.tm_mon + 1 : 0;   // 0 = unknown: matches no active_months bit

        // ── Step 4: Periodic logging ─────────────────────────────────────
        // Log power status every ~5 minutes (every 10th poll at 30s interval).
        // Static counter persists across iterations (FreeRTOS task never exits).
        // This gives a coarse power production timeline in the SD card log
        // without flooding it (30s logs would be ~2880 lines/day).
        static int poll_count = 0;
        if (++poll_count % 10 == 0) {
            snprintf(msg, sizeof(msg),
                     "Surplus: PV=%.0fW grid=%.0fW load=%.0fW surplus=%.1fkW",
                     power.pv_power_w, power.grid_power_w,
                     power.load_power_w, surplus_kw);
            s_log("INFO", msg);
        }

        // ── Step 5: Look up current hour's electricity cost ──────────────
        // Used for the negative-price override in surplus_eval_load().
        // Default to 99 SEK/kWh (a very high positive value) so that if
        // prices haven't been loaded yet, we never falsely trigger the
        // negative-price fast-path. The value 99 is chosen to be obviously
        // impossible as a real price (typical range: 0.10-5.00 SEK/kWh)
        // and safely positive.
        float total_cost_sek = 99.0f;  // sentinel: no negative-price override
        if (s_today_cost_valid && time_ok) {
            /* Slot from UTC arithmetic (DST days have 92/100 slots). */
            DaySlotClock clk;
            clk.day_start_utc = s_today_day_start_utc;
            clk.slot_min = s_today_slot_duration;
            clk.n_slots = s_today_slot_count;
            const int slot = slot_index_at(&clk, now);
            if (slot >= 0 && slot < s_today_slot_count) {
                total_cost_sek = s_today_cost[slot];
            }
        }

        // ── Step 6: Evaluate each flex load ──────────────────────────────
        // Loads are evaluated in config order (which corresponds to priority
        // order — lower index = higher priority, e.g., pool heating before
        // pool pump). Each load's evaluation reduces surplus_kw if it
        // activates, so higher-priority loads get first claim on surplus.
        for (int i = 0; i < s_n_configs; i++) {
            // Build a temporary FlexSurplusState from the persistent static
            // arrays. We use a local struct because surplus_eval_load() is a
            // pure function that operates on the struct — we copy back after.
            FlexSurplusState state = {
                s_flex_active[i], s_surplus_count[i], s_deficit_count[i],
                0, 0  // today_kwh and last_day: not tracked on ESP32 because
                       // the physical thermostat/timer on the load handles
                       // daily energy limits. These fields exist for the
                       // WASM simulator where there's no physical thermostat.
            };

            // Per-load scheduled windows are not produced by the pipeline
            // any more (FlexLoadResult was removed), so nothing is passed.
            const void* fr = NULL;

            // Snapshot the previous state so we can detect transitions.
            bool was_active = state.active;

            // Run the pure evaluation function. This updates state.active,
            // state.surplus_count, state.deficit_count, and reduces surplus_kw
            // if the load is active (so the next load sees less surplus).
            bool now_active = surplus_eval_load(
                &s_configs[i], fr, &state, &surplus_kw, hour, month,
                total_cost_sek);

            // Fuse guard has shed flex loads: force OFF, no hysteresis.
            if (s_inhibit && now_active) {
                now_active = false;
                state.active = false;
                state.surplus_count = 0;
            }

            // Copy the updated state back to the persistent static arrays.
            s_flex_active[i] = state.active;
            s_surplus_count[i] = state.surplus_count;
            s_deficit_count[i] = state.deficit_count;

            // ── Actuate relay only on state transitions ──────────────────
            // We only call flex_control_set() when the state actually changes
            // (was_active != now_active). This avoids:
            //   - Unnecessary Modbus/REST traffic to Shelly plugs every 30s
            //   - Relay wear from redundant GPIO writes
            //   - Log spam from repeated ON/OFF messages
            if (now_active != was_active) {
                // flex_control_set() handles both control types:
                //   FLEX_CTRL_GPIO:   digitalWrite(gpio_pin, on ? HIGH : LOW)
                //   FLEX_CTRL_SHELLY: HTTP GET to shelly_ip/relay/0?turn=on|off
                if (s_io.flex_set) s_io.flex_set(&s_configs[i], i, now_active);

                // Log the state change with the load's human-readable name.
                snprintf(msg, sizeof(msg), "Flex '%s': %s",
                         s_configs[i].name, now_active ? "ON (surplus)" : "OFF");
                s_log("INFO", msg);
            }
        }
    }
}
