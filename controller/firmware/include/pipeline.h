#pragma once

#include "scheduler.h"
#include "config.h"
#include "tuya_client.h"
#include "tou_window.h"
#include "time_local.h"
#include "battery_plan.h"
#include "house_learn.h"

// ── Hardware Abstraction ───────────────────────────────────────────────

struct PipelineGoeStatus {
    bool  car_connected = false;
    int   current_amps  = 0;
    float soc_percent   = -1.0f;  // -1 if unknown
};

struct PipelinePowerStatus {
    float grid_power_w  = 0.0f;  // total grid draw (W), negative = export
    float load_power_w  = 0.0f;  // household load (W)
    float pv_power_w    = 0.0f;  // solar production (W)
    // Per-phase from Tibber Pulse (0 if not available)
    float current_l1_a  = 0.0f;
    float current_l2_a  = 0.0f;
    float current_l3_a  = 0.0f;
    float max_phase_a   = 0.0f;  // highest phase current
    bool  has_per_phase = false;  // true if Pulse data available
};

// ── Flex Load Configuration ───────────────────────────────────────────
constexpr int FLEX_SCHED_SOLAR = 1;  // surplus-activated only

struct FlexLoadConfig {
    char  name[24]      = {};
    float power_kw      = 0.0f;
    float daily_kwh     = 0.0f;
    int   control_type  = 0;     // FLEX_CTRL_GPIO, FLEX_CTRL_SHELLY, or FLEX_CTRL_TUYA
    int   gpio_pin      = 0;
    char  shelly_ip[16] = {};
    TuyaDevice tuya_dev = {};    // Tuya local protocol device (for FLEX_CTRL_TUYA)
    int   active_months = 0;     // bitmask: bit 0 = Jan, bit 11 = Dec
    int   priority      = 0;
    int   sched_mode    = 0;
};

// Charge windows for the Deye program: see tou_window.h

// ── Pipeline I/O — hardware abstraction via function pointers ────
// This struct lets the same pipeline code run on real ESP32 hardware
// and in desktop simulation. Each callback talks to a different backend.
struct PipelineIO {
    // Time
    int now_year = 0, now_month = 0, now_day = 0, now_hour = 0, now_minute = 0;
    int tomorrow_year = 0, tomorrow_month = 0, tomorrow_day = 0;

    // Hardware callbacks (function pointers)
    // Why not std::function? On ESP32 with 520KB SRAM, std::function adds
    // heap allocation per callback. Raw function pointers are zero-cost.
    bool (*read_battery_soc)(float* soc_out)                         = nullptr;
    int  (*fetch_prices)(int year, int month, int day,
                         float* prices_out, int max_slots,
                         int* slot_duration_out)                     = nullptr;
    bool (*set_charge)(int start_min, int end_min, int target_soc)   = nullptr;
    bool (*set_charge_windows)(const TouWindow* windows, int n_windows) = nullptr;
    // Full-day program (≤ 6 segments: grid charge on/off + SOC target/floor).
    // Preferred over set_charge_windows when set (the windows path cannot
    // HOLD the battery for later hours).
    bool (*set_program)(const ProgSegment* segs, int n_segs)         = nullptr;
    // Optional forecasts for a day: fill kwh_out[0..clk->n_slots-1] (kWh per
    // price slot, local time via clk). false / nullptr = default model
    // (solar: cos³ monthly model × SOLAR_KWP; load: the house model, see
    // forecast_temp_c and config.h "Expected house load").
    bool (*forecast_solar_kwh)(const DaySlotClock* clk, int month, float* kwh_out) = nullptr;
    bool (*forecast_load_kwh)(const DaySlotClock* clk, int month, float* kwh_out)  = nullptr;
    // Optional outdoor temperature forecast for a day: fill
    // temp_c_out[0..clk->n_slots-1] (°C per price slot). Used by the house
    // load model when forecast_load_kwh gives nothing. false / nullptr, or an
    // implausible value for a slot = the normal temperature of the month.
    bool (*forecast_temp_c)(const DaySlotClock* clk, int month, float* temp_c_out) = nullptr;
    // What the controller has learned about the house (house_learn.h), or
    // nullptr = the calibrated numbers in config.h. The house model uses the
    // learned base load / heat loss / hourly habit once there are enough days.
    const HouseLearnState* house_learn = nullptr;
    // Planning margin on the house model's load (RuntimeSettings, default
    // HOUSE_LOAD_PLAN_FACTOR). Not applied to an explicit forecast_load_kwh.
    float load_plan_factor = HOUSE_LOAD_PLAN_FACTOR;
    bool (*set_idle)()                                               = nullptr;
    bool (*get_goe_status)(PipelineGoeStatus* status_out)            = nullptr;
    bool (*set_goe_amps)(int max_amps)                               = nullptr;  // 0 = pause (frc=1)
    bool (*read_power_status)(PipelinePowerStatus* status_out)       = nullptr;
    void (*log_msg)(const char* level, const char* msg)              = nullptr;
    void (*show_status)(const char* l1, const char* l2,
                        const char* l3, const char* l4)              = nullptr;
    void (*show_error)(const char* msg)                              = nullptr;
    void (*delay_ms)(unsigned long ms)                               = nullptr;

    // Flex loads
    FlexLoadConfig flex_loads[MAX_FLEX_LOADS] = {};
    int n_flex_loads = 0;
};

// ── Pipeline result ────────────────────────────────────────────────────

struct PipelineResult {
    DaySchedule schedule;                // variable-slot charge/idle schedule
    float       bat_charge_kw  = 0.0f;   // fuse-limited charge rate
    float       fuse_available = 0.0f;   // total fuse headroom
    int         goe_amps       = 0;      // EV charger amps
    int         ev_slots[MAX_SLOTS] = {};// EV charge slot indices
    int         n_ev_slots     = 0;
    float       ev_target_soc  = 0.0f;
    bool        prices_ok      = false;  // true if prices were fetched
    bool        ev_first       = false;  // battery/EV order chosen: EV first
    // Compat aliases
    #define ev_hours ev_slots
    #define n_ev_hours n_ev_slots
};

// ── Entry points ──────────────────────────────────────────────────────

// Legacy single-call API (tests, sim/sil_main.cpp): fetch TOMORROW's prices
// (io->tomorrow_*) and compute a schedule. Does NOT apply anything to the
// Deye — tomorrow's plan is never applied to today. The controller uses
// pipeline_prepare_day / pipeline_activate_day / pipeline_step instead.
bool pipeline_run(const PipelineIO* io, PipelineResult* result);

// Per-slot status from pipeline_apply_slot
struct PipelineSlotStatus {
    int   slot               = 0;
    int   start_min          = 0;
    bool  charging           = false;
    float battery_soc        = 0.0f;   // current SOC (%)
    float battery_power_w    = 0.0f;   // charge power (W), 0 if idle/discharging
    float grid_power_w       = 0.0f;
    float grid_amps_per_phase = 0.0f;
    float load_power_w       = 0.0f;
    float pv_power_w         = 0.0f;
    float fuse_headroom_pct  = 100.0f;
    bool  fuse_limited       = false;
    bool  pool_hp_on         = false;  // pool heat pump running (solar surplus)
    int   grid_reward        = 0;      // 0=none, 1=increase(charge), 2=decrease(pause)
};

// Backward compat
using PipelineHourStatus = PipelineSlotStatus;

// Apply the schedule for the current slot.
void pipeline_apply_slot(const PipelineIO* io, const PipelineResult* result,
                         int slot, PipelineSlotStatus* status_out);

// ── Rolling evaluation (one slot at a time) ─────────────────────────
// Re-evaluates the charge decision each slot based on live state.

struct PipelineDayContext {
    float prices[MAX_SLOTS]  = {};       // today's prices (fetched once)
    int   n_prices           = 0;
    int   slot_duration_min  = 0;
    int   year = 0, month = 0, day = 0;
    float bat_charge_kw      = 0.0f;     // fuse-limited charge rate
    float fuse_available_kw  = 0.0f;
    int   goe_amps           = 0;
    // Look-ahead plan (computed once, followed unless conditions change)
    bool  plan[MAX_SLOTS]    = {};       // true = charge this slot
    bool  plan_valid         = false;    // true if plan has been computed
    float plan_soc           = 0.0f;    // SOC the plan was computed for
    // TOU window state (written once, not every slot)
    bool  tou_written        = false;    // true after TOU windows sent to Deye
    TouWindow tou_windows[MAX_TOU_WINDOWS] = {};
    int   tou_n_windows      = 0;
    // Day program (planner output): ≤ 6 segments covering the local day
    ProgSegment prog[MAX_PROG_SEGMENTS] = {};
    int   n_prog             = 0;
    float plan_value_sek     = 0.0f;     // expected battery net (Deye model)
    // EV plan: go-e amps per price slot (0 = not planned)
    uint8_t ev_amps[MAX_SLOTS] = {};
    float ev_planned_kwh     = 0.0f;
    float ev_cost_sek        = 0.0f;     // planned EV energy cost
    // Battery/EV fuse budget order (EV_PRIORITY_MODE, plan_shared_day)
    bool  ev_absent          = false;    // plan without EV demand (no car)
    bool  ev_first           = false;    // order chosen: EV first
    bool  ev_order_compared  = false;    // AUTO evaluated both orders
    float ev_order_gain_sek  = 0.0f;     // other order's total − chosen (≥ 0)
    // Forecast at planning resolution (pipeline_fill_forecast)
    float fc_solar_kwh[PLAN_MAX_SLOTS] = {};
    float fc_load_kwh[PLAN_MAX_SLOTS]  = {};
    bool  fc_valid           = false;
    // Where the load forecast came from (FC_LOAD_*), the day's expected
    // house load, and the mean outdoor temperature the house model used.
    int   fc_load_source     = 0;
    float fc_load_day_kwh    = 0.0f;
    float fc_temp_mean_c     = 0.0f;
    int   fc_house_fit       = 0;        // HOUSE_FIT_*: prior / level / full
    float fc_load_factor     = 1.0f;     // planning margin applied to fc_load_kwh
                                         // (fc_load_day_kwh includes it)
    // Looking ahead (pipeline_try_lookahead): what energy left at the end of
    // this day is worth tomorrow. end.n = 0 = unknown → planned as a single day.
    PlanEnd end;
    float lookahead_gain_sek = 0.0f;     // expected gain of the plan with `end`
                                         // over the same plan without it
    float end_reserved_kwh   = 0.0f;     // stored kWh the plan keeps for tomorrow
};

// PipelineDayContext::fc_load_source
constexpr int FC_LOAD_NONE          = 0;  // not filled
constexpr int FC_LOAD_CALLBACK      = 1;  // PipelineIO::forecast_load_kwh
constexpr int FC_LOAD_MODEL_FC_TEMP = 2;  // house model, forecast temperature
constexpr int FC_LOAD_MODEL_NORMAL  = 3;  // house model, normal temp of the month
constexpr int FC_LOAD_PROFILE       = 4;  // HOUSE_LOAD_PROFILE_KW (model switched off)

// Price slots per planning slot: 1 up to PLAN_MAX_SLOTS price slots,
// otherwise ceil(n / PLAN_MAX_SLOTS) (1-min prices → 15-min planning).
int pipeline_plan_group(int n_prices);

// Fill ctx->fc_* from io's forecast callbacks (or the default models when
// io / a callback is null or fails). Needs n_prices, slot_duration_min, date.
// Load: forecast_load_kwh, else the house model (house_load.h) at the
// forecast_temp_c temperature, else the house model at the month's normal
// temperature (see config.h "Expected house load").
void pipeline_fill_forecast(const PipelineIO* io, PipelineDayContext* ctx);
// Log the day's load forecast and where it came from (io->log_msg).
void pipeline_log_load_forecast(const PipelineIO* io, const PipelineDayContext* ctx);

// Buying cost (SEK/kWh) of a price slot: spot × VAT + grid fee + tax.
float pipeline_slot_buy_cost(const PipelineDayContext* ctx, int slot);

// Plan the day from from_slot with the live SOC (%):
//   1. buying cost per slot, expected load/solar (ctx->fc_*, defaults if
//      not filled), grid-charge room per slot from the fuse budget
//   2. EV plan (cheapest slots in its window) and battery plan
//      (bat_plan_day) sharing the budget (plan_shared_day): order per
//      EV_PRIORITY_MODE — fixed, or AUTO = the cheaper day of both orders.
//      ctx->ev_absent → no EV demand, the battery gets the full budget
//   3. battery plan → ≤ 6 program segments (ctx->prog), ctx->plan[i] = the
//      Deye may grid-charge in slot i
// Slots before from_slot keep their old plan[] values.
void pipeline_plan(PipelineDayContext* ctx, float current_soc, int from_slot);
// Same with an explicit battery/EV order mode (tests, tools).
void pipeline_plan_mode(PipelineDayContext* ctx, float current_soc, int from_slot,
                        EvPriorityMode mode);
// Log the chosen battery/EV order and the kr difference (io->log_msg).
void pipeline_log_ev_order(const PipelineIO* io, const PipelineDayContext* ctx);

// UTC slot clock of a day context (local midnight of year/month/day,
// slot_duration_min, n_prices). Slot i ↔ local time via time_local.h.
DaySlotClock pipeline_day_clock(const PipelineDayContext* ctx);

// Contiguous charge blocks of ctx->plan from from_slot → TouWindows in LOCAL
// minutes (end 1440 = end of day). Returns the number of windows (≤ max).
int pipeline_plan_to_windows(const PipelineDayContext* ctx, int from_slot,
                             TouWindow* windows, int max_windows,
                             int target_soc, int charge_power_w);

// Tomorrow's prices have arrived: work out what energy carried into
// `tomorrow` is worth (bat_end_tranches on its prices and forecast) and
// re-plan the rest of `today` from from_slot with the live SOC. The new plan
// replaces today's only if it is expected to be worth at least
// PLAN_LOOKAHEAD_MIN_GAIN_SEK more than planning the rest of the day on its
// own; today is then marked for a program rewrite at the next step. Returns
// true if adopted. Otherwise today is left exactly as it was.
bool pipeline_try_lookahead(const PipelineIO* io, PipelineDayContext* today,
                            const PipelineDayContext* tomorrow, int from_slot);
// The PlanEnd of a prepared day context (prices + forecast), for the day before.
void pipeline_day_end_value(const PipelineDayContext* next_day, PlanEnd* out);

// 13:30: fetch prices for the given (tomorrow's) date into ctx, set the fuse
// budget and a provisional plan. ctx must be a SEPARATE "tomorrow" context:
// it is never applied before its own date. False = no prices (ctx zeroed).
bool pipeline_prepare_day(const PipelineIO* io, PipelineDayContext* ctx,
                          int year, int month, int day);

// Local midnight: the stored context becomes today's. Forces a replan from
// the live SOC and a (daily) rewrite of the Deye program at the next step.
void pipeline_activate_day(PipelineDayContext* ctx);

// Grid reward signal from Tibber (frequency response)
// In C++14, enum class is preferred over plain enum — it prevents
// implicit conversion to int and avoids name collisions.
// We keep plain enum here for backward compat with C-style switch statements.
enum GridRewardSignal {
    GRID_REWARD_NONE     = 0,  // no active signal
    GRID_REWARD_INCREASE = 1,  // "consume more" — charge battery
    GRID_REWARD_DECREASE = 2,  // "consume less" — pause charging
};

// Evaluate a single slot. Reads live SOC + power, decides charge/idle.
void pipeline_step(const PipelineIO* io, PipelineDayContext* ctx,
                   int slot, GridRewardSignal grid_signal,
                   PipelineSlotStatus* status_out);
