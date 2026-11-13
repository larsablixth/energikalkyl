/**
 * @file controller.cpp
 * @brief The controller's decisions — moved here unchanged from main.cpp
 *
 * See controller.h. Every function below was in main.cpp; the only changes
 * are that hardware, time and storage go through ControllerHw instead of the
 * drivers / time() / millis() / SD directly, and that the task loops are
 * split into one-iteration ticks.
 *
 * Scheduler tick (all decisions in plan_state.h):
 *   - local midnight: TOMORROW's stored plan becomes today's (never earlier);
 *     no plan for today → safe program
 *   - from 13:30: fetch tomorrow's prices + provisional plan into a separate
 *     context; retry every 15 min until 23:00, then give up (tomorrow safe)
 *   - after a reboot mid-day: fetch TODAY's prices so the day is not lost
 *   - first slot after tomorrow's prices: look-ahead re-plan of today
 *   - each slot boundary: pipeline_step(today) — writes the Deye program
 *     once per day (or on refresh / after an override), monitors SOC/fuse
 *   - once a minute: the house load reading for the house learning
 *   - safety: invalid time, repeated Modbus failures, a grid-charge program
 *     older than 26 h or past its day's expiry → safe program
 */

#include "controller.h"
#include "config.h"
#include "scheduler.h"
#include "deye_program.h"
#include "surplus_task.h"
#include "house_meter.h"
#include "house_load.h"
#include "time_local.h"
#include <cstring>
#include <cstdio>

namespace {

// ── Hardware, clock, output ───────────────────────────────────────────────

ControllerHw hw_;
ControllerConfig cfg_;
FlexLoadConfig flex_[MAX_FLEX_LOADS];

time_t   now_utc() { return hw_.now_utc ? hw_.now_utc() : 0; }
uint32_t now_ms()  { return hw_.now_ms ? hw_.now_ms() : 0; }

void log_msg(const char* level, const char* msg) {
    if (hw_.log_msg) hw_.log_msg(level, msg);
}
void show_error(const char* msg) {
    if (hw_.show_error) hw_.show_error(msg);
}
void feed_watchdog() {
    if (hw_.feed_watchdog) hw_.feed_watchdog();
}

struct Lock {
    bool ok;
    Lock() : ok(hw_.lock ? hw_.lock() : true) {}
    ~Lock() { if (ok && hw_.unlock) hw_.unlock(); }
};

// ── State (was main.cpp statics) ─────────────────────────────────────────

/** Today's and tomorrow's plan. Large (~10 KB each) → static, never on a
 *  task stack. Written only by the scheduler tick; display reads a few
 *  scalars (stale reads are harmless). */
PipelineDayContext g_today;
PipelineDayContext g_tomorrow;
volatile bool g_today_valid    = false;
volatile bool g_tomorrow_valid = false;
int g_last_slot = -1;

FetchRetryState g_fetch_tomorrow;
FetchRetryState g_fetch_today;
const FetchRetryConfig FETCH_TOMORROW_CFG = {
    SCHEDULE_HOUR * 60 + SCHEDULE_MINUTE, PRICE_RETRY_INTERVAL_MIN, PRICE_RETRY_DEADLINE_MIN};
/** Rebooted mid-day without a plan for today: try today's prices too. */
const FetchRetryConfig FETCH_TODAY_CFG = {0, PRICE_RETRY_INTERVAL_MIN, 23 * 60 + 45};

/** Deye program bookkeeping for the safe-state decision. */
volatile int64_t g_plan_written_utc = 0;   // last verified grid-charge program
volatile int64_t g_plan_expires_utc = 0;
/** Safe program must be (re)written + verified before any plan write.
 *  Updated every scheduler tick by safe_pending_next() (plan_state.h). */
volatile bool g_safe_pending = true;
SafetyAction  g_safe_reason  = SAFETY_TIME_INVALID;
uint32_t      g_last_safe_attempt_ms = 0;
/** Fuse guard released the battery: rewrite today's program next slot. */
volatile bool g_tou_restore_pending = false;

volatile bool g_safe_hold      = true;    /* boot: until confirmed */
volatile bool g_safe_confirmed = false;
volatile bool g_boot_safe_ok   = false;   /* safe program ever verified */

/** now_ms() of the last scheduler tick with valid time (26 h watchdog). */
volatile uint32_t g_last_scheduler_run_ms = 0;

// ── Fuse guard shared state ───────────────────────────────────────────────
/** Decision published by the fuse guard; read by the scheduler-side
 *  wrappers so a plan can never override an active shed. Single-word
 *  volatile values: written by one task, read by others. */
FuseGuardState  g_guard;
FuseGuardStatus g_guard_status;
volatile int  g_guard_goe_cap     = 0;     // -1 = no cap, 0 = paused, else amps
volatile bool g_guard_bat_inhibit = true;  // fail-safe until the guard has run
/** go-e amps the planner asked for; -1 = planner has not controlled it yet. */
volatile int  g_goe_planned_amps  = -1;
/** Last go-e state we commanded (for the guard when status read fails). */
volatile int  g_goe_applied_amps  = 0;
volatile bool g_goe_stopped_by_us = false;
/** Last go-e status seen (any task that polls it): is the car charging, and
 *  when was that read. Used to keep EV charging out of the house learning. */
volatile bool     g_goe_charging_seen = false;
volatile uint32_t g_goe_status_ms     = 0;
volatile bool     g_goe_status_valid  = false;

/** Tomorrow's prices have arrived and today has not been re-planned with
 *  them yet (scheduler only). Cleared at the midnight swap. */
bool g_lookahead_pending = false;

// ── House learning state (scheduler only) ─────────────────────────────────
HouseLearnState g_house_learn;       // what has been learned (saved through storage)
HouseDayLog     g_house_log;         // the day being measured
HouseTempStore  g_house_temps;       // forecast temperatures per day
time_t          g_house_last_sample = 0;

PipelineIO  g_io;
FuseGuardIO g_guard_io;
int g_scheduler_ticks = 0, g_guard_ticks = 0, g_surplus_ticks = 0;
ControllerView g_view;

// ── go-e ──────────────────────────────────────────────────────────────────

void note_goe_status(const GoeStatus& raw) {
    g_goe_charging_seen = raw.charging;
    g_goe_status_ms = now_ms();
    g_goe_status_valid = true;
}

/** Write the effective go-e setpoint: <GOE_MIN_AMPS → pause (frc=1). */
bool goe_apply(int amps) {
    /* Called from scheduler AND fuse guard: hold the (recursive) bus lock so
     * the stop/limit/release sequence and its bookkeeping are atomic. */
    Lock lock;
    if (!lock.ok) return false;
    if (amps < GOE_MIN_AMPS) {
        if (!g_goe_stopped_by_us) {
            if (!hw_.goe_stop_charging || !hw_.goe_stop_charging()) return false;
            g_goe_stopped_by_us = true;
        }
        g_goe_applied_amps = 0;
        return true;
    }
    if (amps > GOE_MAX_AMPS) amps = GOE_MAX_AMPS;
    if (!hw_.goe_set_amps || !hw_.goe_set_amps(amps)) return false;
    if (g_goe_stopped_by_us) {
        if (!hw_.goe_release_stop || !hw_.goe_release_stop()) return false;
        g_goe_stopped_by_us = false;
    }
    g_goe_applied_amps = amps;
    return true;
}

/** min(planner request, guard cap). Returns -1 if there is nothing to write
 *  (planner never set a value and no guard cap). */
int goe_effective(int planned, int cap) {
    if (planned < 0) return cap;          /* not planner-controlled: cap only */
    if (cap < 0) return planned;
    return (planned < cap) ? planned : cap;
}

// ── Pipeline callbacks (PipelineIO) ───────────────────────────────────────

bool io_read_battery_soc(float* soc_out) {
    return hw_.deye_read_soc && hw_.deye_read_soc(soc_out);
}

int io_fetch_prices(int year, int month, int day, float* prices_out, int max_slots,
                    int* slot_duration_out) {
    return hw_.fetch_prices ? hw_.fetch_prices(year, month, day, prices_out, max_slots,
                                               slot_duration_out) : 0;
}

/** Outdoor temperature forecast for the house load model. Asked for by the
 *  pipeline when it prepares a day — the same step that fetches the day's
 *  prices. false = plan with the month's normal temperature. */
bool io_forecast_temp(const DaySlotClock* clk, int month, float* temp_c_out) {
    if (!hw_.forecast_temp_c || !hw_.forecast_temp_c(clk, month, temp_c_out)) {
        return false;
    }
    /* Remember the forecast as that day's temperature for the learning. */
    house_temp_put(&g_house_temps, local_date_of(clk->day_start_utc), clk, temp_c_out);
    return true;
}

/** Record a verified program write for the safe-state decision. A program
 *  with grid charge carries an explicit expiry: the end of today's local
 *  date (+ grace). The controller rewrites it at the next midnight swap or
 *  falls back to the safe program. */
void note_program_written(bool grid_charge) {
    if (grid_charge) {
        const time_t now = now_utc();
        g_plan_written_utc = static_cast<int64_t>(now);
        g_plan_expires_utc = plan_expiry_utc(local_date_of(now), PLAN_EXPIRY_GRACE_S);
    } else {
        g_plan_written_utc = 0;
        g_plan_expires_utc = 0;
    }
}

/** Grid-charge program writes are refused while the fuse guard has battery
 *  charging paused, while the safe program is pending, or without valid
 *  time. A refusal returns false → the pipeline retries next slot. */
bool charge_write_allowed() {
    if (g_guard_bat_inhibit) {
        log_msg("WARN", "Charge program refused: fuse guard has battery paused");
        return false;
    }
    if (!charge_write_permitted(false, g_safe_pending, time_is_valid(now_utc()))) {
        log_msg("WARN", "Charge program refused: safe state active");
        return false;
    }
    return true;
}

int grid_charge_amps(int max_w) {
    return deye_grid_charge_current_a(static_cast<float>(max_w) / 1000.0f, BATTERY_CHARGE_V_MAX,
                                      DEYE_INVERTER_EFF, DEYE_GRID_CHARGE_MAX_A);
}

bool io_set_charge_windows(const TouWindow* windows, int n_windows) {
    if (!charge_write_allowed()) return false;
    int max_w = 0;
    for (int i = 0; i < n_windows; i++) {
        if (windows[i].charge_power_w > max_w) max_w = windows[i].charge_power_w;
    }
    const bool ok = hw_.deye_set_charge_windows &&
                    hw_.deye_set_charge_windows(windows, n_windows, grid_charge_amps(max_w));
    if (ok) note_program_written(n_windows > 0);
    return ok;
}

/** Planner program: ≤ 6 segments with per-segment grid charge + SOC. */
bool io_set_program(const ProgSegment* segs, int n_segs) {
    bool charges = false;
    int max_w = 0;
    for (int i = 0; i < n_segs; i++) {
        if (segs[i].grid_charge) {
            charges = true;
            if (segs[i].power_w > max_w) max_w = segs[i].power_w;
        }
    }
    /* A program without grid charging (holds/floors only) is always
     * allowed; one that charges needs the same checks as windows. */
    if (charges && !charge_write_allowed()) return false;
    const bool ok = hw_.deye_set_program_segments &&
                    hw_.deye_set_program_segments(segs, n_segs, grid_charge_amps(max_w));
    if (ok) note_program_written(charges);
    return ok;
}

/** Single window (grid reward override). */
bool io_set_charge(int start_min, int end_min, int target_soc) {
    if (!charge_write_allowed()) return false;
    const bool ok = hw_.deye_set_charge && hw_.deye_set_charge(start_min, end_min, target_soc);
    if (ok) note_program_written(true);
    return ok;
}

bool io_set_idle() {
    const bool ok = hw_.deye_set_idle && hw_.deye_set_idle();
    if (ok) note_program_written(false);
    return ok;
}

bool io_get_goe_status(PipelineGoeStatus* status_out) {
    GoeStatus raw;
    if (!hw_.goe_get_status || !hw_.goe_get_status(&raw)) return false;
    note_goe_status(raw);
    status_out->car_connected = raw.car_connected;
    status_out->current_amps  = raw.current_amps;
    status_out->soc_percent   = raw.soc_percent;
    return true;
}

bool io_read_power_status(PipelinePowerStatus* status_out) {
    DeyePowerStatus raw;
    if (!hw_.deye_read_power_status || !hw_.deye_read_power_status(&raw)) return false;
    status_out->grid_power_w = raw.grid_power_w;
    status_out->load_power_w = raw.load_power_w;
    status_out->pv_power_w = raw.pv_power_w;
    return true;
}

/** Planner request for the go-e (amps, 0 = pause). The value actually
 *  written is min(request, fuse guard cap); below GOE_MIN_AMPS → frc=1. */
bool io_set_goe_amps(int max_amps) {
    g_goe_planned_amps = (max_amps > 0) ? max_amps : 0;   /* 0 = pause */
    const int eff = goe_effective(g_goe_planned_amps, g_guard_goe_cap);
    return goe_apply(eff < 0 ? 0 : eff);
}

void io_show_status(const char* l1, const char* l2, const char* l3, const char* l4) {
    if (hw_.show_status) hw_.show_status(l1, l2, l3, l4);
}
void io_delay_ms(unsigned long ms) {
    if (hw_.delay_ms) hw_.delay_ms(ms);
}

void build_pipeline_io() {
    g_io = PipelineIO{};
    g_io.read_battery_soc   = io_read_battery_soc;
    g_io.fetch_prices       = io_fetch_prices;
    g_io.forecast_temp_c    = io_forecast_temp;
    g_io.house_learn        = HOUSE_LEARN_ENABLED ? &g_house_learn : nullptr;
    g_io.load_plan_factor   = cfg_.load_plan_factor;
    g_io.set_charge         = io_set_charge;
    g_io.set_charge_windows = io_set_charge_windows;
    g_io.set_program        = io_set_program;
    g_io.set_idle           = io_set_idle;
    g_io.get_goe_status     = io_get_goe_status;
    g_io.set_goe_amps       = io_set_goe_amps;
    g_io.read_power_status  = io_read_power_status;
    g_io.log_msg            = log_msg;
    g_io.show_status        = io_show_status;
    g_io.show_error         = show_error;
    g_io.delay_ms           = io_delay_ms;
    g_io.n_flex_loads = cfg_.n_flex_loads;
    std::memcpy(g_io.flex_loads, flex_, sizeof(FlexLoadConfig) * cfg_.n_flex_loads);
}

// ── Fuse guard I/O ────────────────────────────────────────────────────────

bool guard_read_meter(TibberPulseData* out) {
    std::memset(out, 0, sizeof(*out));
    return hw_.read_meter && hw_.read_meter(out);
}

int guard_get_goe_amps() {
    GoeStatus raw;
    if (hw_.goe_get_status && hw_.goe_get_status(&raw)) {
        note_goe_status(raw);
        return raw.current_amps;          /* 0 if forced off */
    }
    return g_goe_applied_amps;            /* last commanded (conservative) */
}

bool guard_battery_grid_charging() {
    return hw_.deye_grid_charge_enabled && hw_.deye_grid_charge_enabled();
}
bool guard_hp_running() { return surplus_any_load_active(); }

bool guard_set_goe_limit(int amps) {
    g_guard_goe_cap = amps;
    const int eff = goe_effective(g_goe_planned_amps, amps);
    return goe_apply(eff < 0 ? 0 : eff);
}

bool guard_clear_goe_limit() {
    g_guard_goe_cap = -1;
    if (g_goe_planned_amps >= 0) {
        return goe_apply(g_goe_planned_amps);
    }
    Lock lock;
    if (!lock.ok) return false;
    if (g_goe_stopped_by_us) {
        if (!hw_.goe_release_stop || !hw_.goe_release_stop()) return false;
        g_goe_stopped_by_us = false;
    }
    return true;
}

/** Pause = the safe program (grid charge off everywhere, reg 130 first). */
bool guard_pause_battery() {
    const bool ok = hw_.deye_set_idle && hw_.deye_set_idle();
    if (ok) note_program_written(false);
    return ok;
}

/** Release writes nothing itself: the scheduler rewrites today's program at
 *  the next slot (one EEPROM write cycle, rate-limited by the guard). */
bool guard_resume_battery() {
    g_tou_restore_pending = true;
    log_msg("INFO", "Fuse guard: battery released (program restored next slot)");
    return true;
}

bool guard_set_hp(bool on) {
    return on ? true : surplus_shed_all();   /* the guard only ever turns loads OFF */
}

void guard_publish(const FuseGuardStatus* st) {
    g_guard_goe_cap     = st->goe_reduced ? st->goe_limit_a : -1;
    g_guard_bat_inhibit = st->bat_paused;
    surplus_set_inhibit(st->hp_shed);
}

uint32_t guard_now_ms() { return now_ms(); }

void build_guard_io() {
    g_guard_io = FuseGuardIO{};
    g_guard_io.read_meter            = guard_read_meter;
    g_guard_io.get_goe_amps          = guard_get_goe_amps;
    g_guard_io.battery_grid_charging = guard_battery_grid_charging;
    g_guard_io.hp_running            = guard_hp_running;
    g_guard_io.set_goe_limit         = guard_set_goe_limit;
    g_guard_io.clear_goe_limit       = guard_clear_goe_limit;
    g_guard_io.pause_battery         = guard_pause_battery;
    g_guard_io.resume_battery        = guard_resume_battery;
    g_guard_io.set_hp                = guard_set_hp;
    g_guard_io.publish               = guard_publish;
    g_guard_io.log_msg               = log_msg;
    g_guard_io.now_ms                = guard_now_ms;
    /* delay_ms / feed_watchdog: one step per tick, the task loop sleeps. */
}

// ── Surplus I/O ───────────────────────────────────────────────────────────

bool surplus_goe_status(GoeStatus* out) {
    if (!hw_.goe_get_status || !hw_.goe_get_status(out)) return false;
    note_goe_status(*out);
    return true;
}

// ── Learning the house (house_learn.h, house_meter.h) ─────────────────────

/** Load what was learned; start from scratch if there is nothing stored, or
 *  it is damaged or from another firmware version. */
void house_learn_load() {
    house_learn_reset(&g_house_learn);
    if (!HOUSE_LEARN_ENABLED || !hw_.storage_read) return;
    uint8_t buf[HOUSE_LEARN_BLOB_MAX];
    const int len = hw_.storage_read(HOUSE_LEARN_FILE, buf, static_cast<int>(sizeof(buf)));
    if (len < 0) {
        log_msg("INFO", "House learning: no saved state — starting from the config.h calibration");
        return;
    }
    HouseLearnState s;
    if (!house_learn_deserialize(buf, len, &s)) {
        log_msg("WARN", "House learning: saved state unreadable — starting from scratch");
        return;
    }
    g_house_learn = s;
    char msg[96];
    snprintf(msg, sizeof(msg), "House learning: loaded %u days from storage",
             static_cast<unsigned>(s.days));
    log_msg("INFO", msg);
}

void house_learn_save() {
    if (!hw_.storage_write) return;
    uint8_t buf[HOUSE_LEARN_BLOB_MAX];
    const int len = house_learn_serialize(&g_house_learn, buf, static_cast<int>(sizeof(buf)));
    if (len <= 0) return;
    if (!hw_.storage_write(HOUSE_LEARN_FILE, buf, len)) {
        log_msg("WARN", "House learning: could not save");
    }
}

/** A local day is complete: add it to the fit if it is usable. */
void house_day_finished(const HouseDayResult& day) {
    char msg[128];
    float hour_c[24];
    if (!house_temp_get(&g_house_temps, day.day, hour_c)) {
        snprintf(msg, sizeof(msg), "House learning: %04d-%02d-%02d skipped — no temperature forecast was stored for it",
                 day.day.year, day.day.month, day.day.day);
        log_msg("INFO", msg);
        return;
    }
    const HouseLoadModel prior = house_load_default();
    if (!house_learn_add_day(&g_house_learn, prior, day.hour_kwh, hour_c, HOUSE_LEARN_MEMORY_DAYS)) {
        snprintf(msg, sizeof(msg), "House learning: %04d-%02d-%02d skipped — only %d of 24 hours measured",
                 day.day.year, day.day.month, day.day.day, day.valid_hours);
        log_msg("INFO", msg);
        return;
    }
    HouseLoadModel m;
    const int fit = house_learn_model(&g_house_learn, prior, &m);
    snprintf(msg, sizeof(msg), "House learning: %04d-%02d-%02d added (%u days). %s base %.2f kW, heat loss %.3f kW/C",
             day.day.year, day.day.month, day.day.day, static_cast<unsigned>(g_house_learn.days),
             fit == HOUSE_FIT_FULL ? "Learned:" : fit == HOUSE_FIT_LEVEL ? "Base learned:" : "Not used yet:",
             m.base_kw, m.h_loss_kw_per_c);
    log_msg("INFO", msg);
    house_learn_save();
}

/** Read the house load about once a minute and collect it into days. */
void house_sample(time_t now) {
    if (!HOUSE_LEARN_ENABLED) return;
    if (g_house_last_sample != 0 && now >= g_house_last_sample &&
        now - g_house_last_sample < HOUSE_SAMPLE_INTERVAL_S) {
        return;
    }
    g_house_last_sample = now;

    DeyePowerStatus raw;
    /* failures here do not count for safety */
    bool valid = hw_.deye_sample_power_status && hw_.deye_sample_power_status(&raw);
    /* With the go-e behind the Deye CT the "load" includes the car. Leave
     * those minutes out: a fresh status says whether it is charging; without
     * one, assume it is whenever we last commanded it on. */
    if (valid && DEYE_CT_SEES_GOE) {
        const bool fresh = g_goe_status_valid && (now_ms() - g_goe_status_ms) < 120000UL;
        const bool ev_charging = fresh ? static_cast<bool>(g_goe_charging_seen)
                                       : (g_goe_applied_amps > 0);
        if (ev_charging) valid = false;
    }
    HouseDayResult done;
    if (house_meter_add(&g_house_log, now, valid ? raw.load_power_w : 0.0f, valid, &done)) {
        house_day_finished(done);
    }
}

// ── Safe state ─────────────────────────────────────────────────────────────
// While a safety condition holds, no plan is written and the safe program
// is written + verified once (retried every SAFE_RETRY_MS until confirmed).
// When the condition clears, today's program is rewritten at once.

bool try_apply_safe() {
    const uint32_t ms = now_ms();
    if (g_last_safe_attempt_ms != 0 && ms - g_last_safe_attempt_ms < SAFE_RETRY_MS) {
        return false;
    }
    g_last_safe_attempt_ms = ms ? ms : 1;
    if (!hw_.deye_apply_safe_program || !hw_.deye_apply_safe_program()) {
        return false;
    }
    note_program_written(false);
    g_boot_safe_ok = true;
    return true;
}

void update_safe_hold(SafetyAction need) {
    char msg[96];
    if (need != SAFETY_OK) {
        if (!g_safe_hold || g_safe_reason != need) {
            snprintf(msg, sizeof(msg), "SAFE program: %s", safety_action_name(need));
            log_msg("ERROR", msg);
        }
        if (!g_safe_hold) {
            g_safe_confirmed = false;
        }
        g_safe_hold = true;
        g_safe_reason = need;
        g_today.tou_written = false;          /* plan rewritten after the hold */
        if (!g_safe_confirmed && try_apply_safe()) {
            g_safe_confirmed = true;
        }
    } else if (g_safe_hold) {
        g_safe_hold = false;
        g_today.tou_written = false;
        g_last_slot = -1;                     /* step (and rewrite) right away */
        log_msg("INFO", "Safe state cleared — following today's plan");
    }
}

// ── Day handling ───────────────────────────────────────────────────────────

LocalDate ctx_date(const PipelineDayContext& c) {
    LocalDate d;
    d.year = c.year; d.month = c.month; d.day = c.day;
    return d;
}

/** Hand TODAY's slot buying costs (spot × VAT + grid fee + energy tax) to
 *  the surplus task (its negative-price override uses the TOTAL cost). */
void publish_today_prices() {
    if (!g_today_valid) {
        surplus_set_today_prices(nullptr, 0, 0, 0);
        return;
    }
    static float costs[MAX_SLOTS];
    scheduler_day_buy_costs(g_today.prices, g_today.n_prices, g_today.slot_duration_min,
                            g_today.year, g_today.month, g_today.day, costs);
    const DaySlotClock clk = pipeline_day_clock(&g_today);
    surplus_set_today_prices(costs, g_today.n_prices, g_today.slot_duration_min,
                             static_cast<int64_t>(clk.day_start_utc));
}

void activate_today(const char* how) {
    g_today_valid = true;
    pipeline_activate_day(&g_today);
    if (hw_.deye_invalidate_cache) hw_.deye_invalidate_cache();   /* daily rewrite reads back again */
    g_last_slot = -1;
    publish_today_prices();
    char msg[96];
    snprintf(msg, sizeof(msg), "Plan for %04d-%02d-%02d active (%s), %d slots x %d min",
             g_today.year, g_today.month, g_today.day, how,
             g_today.n_prices, g_today.slot_duration_min);
    log_msg("INFO", msg);
}

void day_rollover(const LocalDate& today) {
    const RolloverAction a = plan_rollover_decide(g_today_valid, ctx_date(g_today),
                                                  g_tomorrow_valid, ctx_date(g_tomorrow), today);
    if (a == ROLL_SWAP) {
        std::memcpy(static_cast<void*>(&g_today), &g_tomorrow, sizeof(g_today));
        std::memset(static_cast<void*>(&g_tomorrow), 0, sizeof(g_tomorrow));
        g_tomorrow_valid = false;
        g_lookahead_pending = false;      /* it was for the day that just ended */
        activate_today("midnight swap");
        return;
    }
    if (a == ROLL_NO_PLAN && g_today_valid) {
        log_msg("WARN", "Stored plan is not for today — dropped");
        g_today_valid = false;
        publish_today_prices();
    }
    /* A stored "tomorrow" that is not for tomorrow any more is dropped. */
    if (g_tomorrow_valid &&
        !local_date_equal(ctx_date(g_tomorrow), local_date_add_days(today, 1))) {
        g_tomorrow_valid = false;
        std::memset(static_cast<void*>(&g_tomorrow), 0, sizeof(g_tomorrow));
    }
}

void fetch_tomorrow(const LocalDate& today, int now_min) {
    const FetchAction fa = fetch_retry_decide(&g_fetch_tomorrow, FETCH_TOMORROW_CFG, today, now_min);
    if (fa == FETCH_NOW) {
        const LocalDate t = local_date_add_days(today, 1);
        feed_watchdog();
        const bool ok = pipeline_prepare_day(&g_io, &g_tomorrow, t.year, t.month, t.day);
        g_tomorrow_valid = ok;
        if (ok) {
            g_lookahead_pending = true;   /* re-plan the rest of today at the next slot */
        }
        fetch_retry_result(&g_fetch_tomorrow, FETCH_TOMORROW_CFG, ok, now_min);
        if (!ok) {
            char msg[96];
            snprintf(msg, sizeof(msg), "Tomorrow's prices: attempt %d failed, retry in %d min (until %02d:%02d)",
                     g_fetch_tomorrow.attempts, PRICE_RETRY_INTERVAL_MIN,
                     PRICE_RETRY_DEADLINE_MIN / 60, PRICE_RETRY_DEADLINE_MIN % 60);
            log_msg("WARN", msg);
            show_error("Price fetch failed");
        }
    } else if (fa == FETCH_GIVE_UP) {
        g_tomorrow_valid = false;
        std::memset(static_cast<void*>(&g_tomorrow), 0, sizeof(g_tomorrow));
        log_msg("ERROR", "No prices for tomorrow by the deadline — tomorrow starts on the "
                         "SAFE program (no grid charging); today's prices retried after midnight");
    }
}

/** After a reboot (or a missed day) there is no plan for today: fetch
 *  today's prices instead of idling until tomorrow. */
void fetch_today(const LocalDate& today, int now_min) {
    const FetchAction fa = fetch_retry_decide(&g_fetch_today, FETCH_TODAY_CFG, today, now_min);
    if (fa == FETCH_NOW) {
        feed_watchdog();
        const bool ok = pipeline_prepare_day(&g_io, &g_today, today.year, today.month, today.day);
        fetch_retry_result(&g_fetch_today, FETCH_TODAY_CFG, ok, now_min);
        if (ok) {
            activate_today("fetched today");
        }
    } else if (fa == FETCH_GIVE_UP) {
        log_msg("ERROR", "No prices for today — staying on the SAFE program");
    }
}

void step_today(time_t now) {
    if (g_tou_restore_pending) {
        g_tou_restore_pending = false;
        g_today.tou_written = false;
        g_last_slot = -1;
    }
    const DaySlotClock clk = pipeline_day_clock(&g_today);
    const int slot = slot_index_at(&clk, now);
    if (slot < 0 || slot >= g_today.n_prices || slot == g_last_slot) {
        return;
    }
    /* Tomorrow's prices arrived since the last slot: is it worth
     * re-planning the rest of today with tomorrow in view? If so the plan
     * is replaced and pipeline_step() below writes the new program. */
    if (g_lookahead_pending) {
        g_lookahead_pending = false;
        if (g_tomorrow_valid) {
            feed_watchdog();
            pipeline_try_lookahead(&g_io, &g_today, &g_tomorrow, slot);
        }
    }
    PipelineSlotStatus st;
    pipeline_step(&g_io, &g_today, slot, GRID_REWARD_NONE, &st);
    g_last_slot = slot;
}

void reset_state() {
    std::memset(static_cast<void*>(&g_today), 0, sizeof(g_today));
    std::memset(static_cast<void*>(&g_tomorrow), 0, sizeof(g_tomorrow));
    g_today_valid = g_tomorrow_valid = false;
    g_last_slot = -1;
    g_fetch_tomorrow = FetchRetryState{};
    g_fetch_today = FetchRetryState{};
    g_plan_written_utc = g_plan_expires_utc = 0;
    g_safe_pending = true;
    g_safe_reason = SAFETY_TIME_INVALID;
    g_last_safe_attempt_ms = 0;
    g_tou_restore_pending = false;
    g_safe_hold = true;
    g_safe_confirmed = false;
    g_boot_safe_ok = false;
    g_last_scheduler_run_ms = 0;
    fuse_guard_state_init(&g_guard);
    g_guard_status = FuseGuardStatus{};
    g_guard_goe_cap = 0;
    g_guard_bat_inhibit = true;
    g_goe_planned_amps = -1;
    g_goe_applied_amps = 0;
    g_goe_stopped_by_us = false;
    g_goe_charging_seen = false;
    g_goe_status_ms = 0;
    g_goe_status_valid = false;
    g_lookahead_pending = false;
    house_learn_reset(&g_house_learn);
    g_house_log = HouseDayLog{};
    g_house_temps = HouseTempStore{};
    g_house_last_sample = 0;
    g_scheduler_ticks = g_guard_ticks = g_surplus_ticks = 0;
}

}  // namespace

// ── Public API ─────────────────────────────────────────────────────────────

void controller_init(const ControllerHw* hw, const ControllerConfig& cfg) {
    hw_ = hw ? *hw : ControllerHw{};
    cfg_ = cfg;
    if (cfg_.n_flex_loads < 0) cfg_.n_flex_loads = 0;
    if (cfg_.n_flex_loads > MAX_FLEX_LOADS) cfg_.n_flex_loads = MAX_FLEX_LOADS;
    for (int i = 0; i < cfg_.n_flex_loads; i++) flex_[i] = cfg_.flex_loads[i];
    cfg_.flex_loads = flex_;
    reset_state();
    house_learn_load();
    build_pipeline_io();
    build_guard_io();
    SurplusIO sio;
    sio.read_power = hw_.deye_read_power_status;
    sio.goe_status = surplus_goe_status;
    sio.flex_set   = hw_.flex_set;
    sio.log_msg    = log_msg;
    surplus_set_io(&sio);
    surplus_task_init(flex_, cfg_.n_flex_loads, nullptr);
    surplus_set_inhibit(false);
    surplus_set_today_prices(nullptr, 0, 0, 0);
}

bool controller_boot_safe() {
    if (g_boot_safe_ok) return true;
    if (!hw_.deye_apply_safe_program || !hw_.deye_apply_safe_program()) return false;
    note_program_written(false);
    g_boot_safe_ok = true;
    g_safe_confirmed = true;
    return true;
}

void controller_scheduler_tick() {
    const time_t now = now_utc();
    const bool time_ok = time_is_valid(now);
    SafetyAction need = SAFETY_OK;
    g_scheduler_ticks++;

    if (time_ok) {
        g_last_scheduler_run_ms = now_ms();
        struct tm lt;
        time_to_local(now, &lt);
        const LocalDate today = local_date_of(now);
        const int now_min = lt.tm_hour * 60 + lt.tm_min;
        house_sample(now);
        day_rollover(today);
        fetch_tomorrow(today, now_min);
        if (!g_today_valid) {
            fetch_today(today, now_min);
        }
        if (!g_today_valid) {
            need = SAFETY_NO_PLAN;
        }
    }

    SafetyInputs in;
    in.time_valid = time_ok;
    in.grid_charge_programmed = hw_.deye_grid_charge_enabled && hw_.deye_grid_charge_enabled();
    in.now_utc = static_cast<int64_t>(now);
    in.plan_written_utc = g_plan_written_utc;
    in.plan_expires_utc = g_plan_expires_utc;
    in.modbus_failures = hw_.deye_consecutive_failures ? hw_.deye_consecutive_failures() : 0;
    in.max_modbus_failures = DEYE_MAX_CONSECUTIVE_FAILURES;
    in.max_plan_age_s = PLAN_MAX_AGE_S;
    const SafetyAction s = safety_decide(in);
    if (s != SAFETY_OK) {
        need = s;
    } else if (need == SAFETY_OK && !g_boot_safe_ok) {
        need = SAFETY_MODBUS;     /* boot safe program not confirmed yet */
    }
    update_safe_hold(need);
    /* Grid-charge writes stay refused until the boot safe program is
     * verified and the safety conditions are clear (plan_state.h). */
    g_safe_pending = safe_pending_next(g_safe_pending, need, g_boot_safe_ok,
                                       time_ok, g_today_valid);

    if (time_ok && g_today_valid && !g_safe_hold) {
        step_today(now);
    }
}

void controller_guard_tick() {
    g_guard_status = fuse_guard_step(&g_guard, &g_guard_io);
    g_guard_ticks++;
}

void controller_surplus_tick() {
    if (cfg_.n_flex_loads <= 0) return;
    surplus_poll(now_utc());
    g_surplus_ticks++;
}

const ControllerView& controller_view() {
    ControllerView& v = g_view;
    v.today = &g_today;
    v.tomorrow = &g_tomorrow;
    v.today_valid = g_today_valid;
    v.tomorrow_valid = g_tomorrow_valid;
    v.safe_hold = g_safe_hold;
    v.safe_confirmed = g_safe_confirmed;
    v.boot_safe_ok = g_boot_safe_ok;
    v.safe_pending = g_safe_pending;
    v.safe_reason = g_safe_reason;
    v.lookahead_pending = g_lookahead_pending;
    v.last_slot = g_last_slot;
    v.plan_written_utc = g_plan_written_utc;
    v.plan_expires_utc = g_plan_expires_utc;
    v.goe_planned_amps = g_goe_planned_amps;
    v.goe_applied_amps = g_goe_applied_amps;
    v.guard_goe_cap = g_guard_goe_cap;
    v.guard_bat_inhibit = g_guard_bat_inhibit;
    v.guard = g_guard_status;
    v.house_learn = &g_house_learn;
    v.last_scheduler_run_ms = g_last_scheduler_run_ms;
    v.scheduler_ticks = g_scheduler_ticks;
    v.guard_ticks = g_guard_ticks;
    v.surplus_ticks = g_surplus_ticks;
    return v;
}

const PipelineIO* controller_pipeline_io() { return &g_io; }
