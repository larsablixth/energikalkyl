#pragma once
// Pure day planning (no hardware, no logging) — unit-tested natively
// (test/test_battery_plan) and driven unchanged by the backtester
// (sim/backtest.cpp).
//
//   bat_plan_day()        time-ordered battery plan, a C++ port of
//                         energikalkyl batteri.py simulate()'s day planner
//   bat_plan_program()    plan → ≤ DEYE_N_PROGRAMS program segments
//                         {start, grid charge on/off, SOC target/floor}
//   bat_simulate_program  what the Deye does with such a program (self-use
//                         + grid charge to target), money as energikalkyl
//   bat_execute_plan()    energikalkyl's own execution of the plan (ideal
//                         controller that can command discharge) — for the
//                         parity check against energikalkyl only
//   ev_plan_day()         EV: cheapest slots in its availability window
//   solar_model_kwh()     cos³ clear-sky/monthly PV model (energikalkyl
//                         solar.py fallback), default forecast
//
// Energy convention (energikalkyl): "level" = stored kWh above the min-SOC
// floor. Grid charging stores 1:1; the whole round-trip loss is taken on
// discharge (delivered = drained × efficiency).
// Money: SEK/kWh buying cost per slot (tariff_buy_cost). Zero-export: the
// discharge only counts up to the house net load (load − solar).
// "Load" = everything behind the Deye grid CT. With DEYE_CT_SEES_GOE the
// go-e EV draw is part of it (plan_shared_day adds the EV plan per slot):
// in self-use the Deye serves the EV from the battery like any other load,
// so the planner values discharge into EV slots and HOLDs (SOC floor at the
// planned level) where serving the EV is not worth it.

#include <cstdint>
#include "config.h"
#include "plant.h"
#include "tou_window.h"

// Planning resolution limit. Longer price series (1-min) are averaged into
// groups first (pipeline). 100 = a 25-hour DST day of quarter-hours.
constexpr int PLAN_MAX_SLOTS = 100;

struct PlanSlot {
    float buy_cost      = 0.0f;   // SEK/kWh, spot × VAT + grid fee + tax
    float export_value  = 0.0f;   // SEK/kWh received for export (0 = zero-export)
    float grid_room_kwh = 0.0f;   // max grid-charge energy (fuse budget, inverter)
    float load_kwh      = 0.0f;   // expected load behind the Deye CT (incl. EV
                                  // when DEYE_CT_SEES_GOE, see plan_shared_day)
    float solar_kwh     = 0.0f;   // expected PV production
};

// ── Value of energy left in the battery at the end of the day ─────────────
// bat_plan_day() plans one day. Without help it sees no use for energy after
// the last slot, so it never charges for tomorrow and happily empties the
// battery into a cheap evening hour before an expensive morning. Once
// tomorrow's prices are known, PlanEnd tells it what carried-over energy is
// worth: up to PLAN_END_TRANCHES steps, most valuable first.
//   value[e]      SEK per kWh DELIVERED tomorrow
//   room_kwh[e]   delivered kWh that are worth that much
//   pair_bonus[e] added to a (charge today → keep) pair's profit before the
//                 min_spread test, see bat_end_tranches()
// n = 0 (the default): nothing is known about tomorrow — the plan is exactly
// what it was before this existed.
constexpr int PLAN_END_TRANCHES = 8;

struct PlanEnd {
    int   n = 0;
    float value[PLAN_END_TRANCHES]      = {};
    float room_kwh[PLAN_END_TRANCHES]   = {};
    float pair_bonus[PLAN_END_TRANCHES] = {};
};

struct PlanParams {
    float slot_h           = 1.0f;
    float capacity_kwh     = plant().battery_capacity_kwh;
    float min_soc          = plant().battery_min_soc / 100.0f;   // fraction
    float max_soc          = plant().battery_max_soc / 100.0f;   // fraction
    float efficiency       = plant().battery_efficiency;         // round trip
    float max_charge_kw    = plant().inverter_max_bat_kw;        // battery side (solar)
    float max_discharge_kw = plant().inverter_max_bat_kw;
    float min_spread       = plant().min_spread_sek;             // SEK/kWh after losses
    bool  export_enabled   = (EXPORT_PRICE_FACTOR > 0.0f);
    PlanEnd end;                                         // tomorrow (n = 0: unknown)
};

struct BatteryPlan {
    int   n = 0;
    float usable_kwh  = 0.0f;
    float start_level = 0.0f;                    // kWh above floor at start
    float charge_kwh[PLAN_MAX_SLOTS]    = {};    // grid → battery (stored)
    float discharge_kwh[PLAN_MAX_SLOTS] = {};    // battery → loads (delivered)
    float solar_in[PLAN_MAX_SLOTS]      = {};    // expected PV → battery
    float level[PLAN_MAX_SLOTS]         = {};    // stored kWh at END of slot
    float end_reserved_kwh = 0.0f;               // stored kWh planned to be kept
                                                 // for tomorrow (PlanParams::end)
};

// Plan one day (slots from_slot..n-1; earlier slots are left empty).
// Every planned kWh is a (charge slot → later use slot) pair, or a use of
// energy already stored (start level / expected solar). Pairs are taken most
// profitable first (ties: earlier use slot, then earlier charge slot — the
// same order as energikalkyl's stable sort) and only if the battery can hold
// the energy in between. A pair needs  value − cost/eff > min_spread  and
// value > cost/eff. Nothing is charged on a day without such a pair, except
// slots whose TOTAL buying cost is < 0 (paid to consume): those fill the
// remaining room even without a later use (the only addition to energikalkyl).
// With p.end (tomorrow's value of carried energy, see PlanEnd) a "use" can
// also be "keep it for tomorrow": such energy is charged if that pays and is
// not spent on a less valuable slot today (out->end_reserved_kwh).
void bat_plan_day(const PlanSlot* s, int n, int from_slot, const PlanParams& p,
                  float start_level_kwh, BatteryPlan* out);

// What energy carried into the NEXT day is worth, from that day's planning
// slots (buy cost, expected load/solar, grid room) and parameters (p.slot_h
// = that day's slot length). The planner itself is asked: the next day is
// planned (bat_plan_day) and valued (bat_execute_plan) with the battery 0,
// 1/8 … 8/8 full at its start; each step's gain is one PlanEnd step:
//   value      = gain / delivered kWh of the step (never rising)
//   pair_bonus = min_spread × the share of the step that only replaces the
//                next day's own grid charging. That energy would be cycled
//                once either way, so charging it today pays as soon as it is
//                cheaper. The rest enables uses the next day could not serve
//                — a new cycle, which must clear min_spread as usual.
// This sees what the next day's plan sees: prices, sun (carried energy is
// worth little if the PV fills the battery anyway), charge room, capacity.
// Nine plans of the next day: a fraction of a second, once a day.
void bat_end_tranches(const PlanSlot* next, int n, const PlanParams& p, PlanEnd* out);

// Worth (SEK) of end_level_kwh stored at the end of the day: the PlanEnd
// steps first, anything beyond them at fallback_per_stored_kwh. With
// p.end.n == 0 this is exactly end_level_kwh × fallback_per_stored_kwh.
float bat_end_worth(const PlanParams& p, float end_level_kwh, float fallback_per_stored_kwh);

// ── Program segments (what the Deye can execute) ─────────────────────────
// The Deye cannot be told to discharge: outside grid charging it serves the
// house from the battery until the program SOC. So the plan becomes:
//   GRID segment: grid charge ON up to soc_pct (also the floor)
//   SELF segment: grid charge OFF, battery not discharged below soc_pct
//                 (= HOLD when soc_pct is the current level, USE when low)
struct PlanSegment {
    int  start_slot  = 0;    // first plan slot of the segment
    bool grid_charge = false;
    int  soc_pct     = plant().battery_min_soc;
};

// Plan → at most max_segments segments; segment 0 starts at slot 0 (slots
// before from_slot get the settings of from_slot). Per-slot settings are
// merged where that costs nothing (GRID slots only with the same program
// power: a GRID segment spanning EV slots would charge at the EV slots'
// small room everywhere); while more than max_segments remain, the
// adjacent merge that loses the least money (bat_simulate_program on the
// expected load/solar, leftover energy valued at half the day's cheapest
// buying cost per delivered kWh) is applied. Returns the number of segments.
int bat_plan_program(const BatteryPlan* plan, const PlanSlot* s, int from_slot,
                     const PlanParams& p, int max_segments, PlanSegment* segs);

// What a program is expected to be worth from from_slot to the end of the
// day (SEK): the Deye model's net on the given slots plus the worth of the
// energy left at the end (PlanParams::end, else the same fallback as
// bat_plan_program: half the cheapest remaining buying cost). Used to decide
// whether a re-planned program is enough better to be worth writing.
float bat_program_objective(const PlanSegment* segs, int n_segs, const PlanSlot* s,
                            int n, int from_slot, const PlanParams& p,
                            float start_level_kwh);

// Result of running a day (money as energikalkyl, SEK).
struct DayMoney {
    float charge_cost     = 0.0f;   // Σ grid-charge kWh × buy cost
    float discharge_value = 0.0f;   // Σ delivered kWh × buy cost (+ export)
    float charged_kwh     = 0.0f;
    float discharged_kwh  = 0.0f;
    float solar_in_kwh    = 0.0f;
    float end_level       = 0.0f;   // kWh above floor
    float net() const { return discharge_value - charge_cost; }
};

// Program power of GRID segment k (kW): the smallest grid room of its slots
// (from from_slot on) — what pipeline_plan writes as the point's power. The
// Deye charges at that power anywhere in the segment, and the program is
// written once a day (the runtime only pauses charging on low headroom /
// the fuse guard), so the power must be fuse-safe in EVERY slot of the
// segment. 0 for SELF segments.
float bat_segment_power_kw(const PlanSegment* segs, int n_segs, int k, const PlanSlot* s,
                           int n, int from_slot, float slot_h);

// Deye model: per slot, PV surplus charges first (≤ max_charge_kw, ≤ max
// SOC); a GRID slot below target charges from the grid (≤ min(grid_room,
// segment power, see bat_segment_power_kw) − PV charge); otherwise the
// battery covers the net load down to the segment's SOC (≤ max_discharge_kw;
// zero-export: never more than the net load).
DayMoney bat_simulate_program(const PlanSegment* segs, int n_segs, const PlanSlot* s,
                              int n, int from_slot, const PlanParams& p,
                              float start_level_kwh);
// The same for slots [from_slot, to_slot) only — the program still covers
// all n slots (a GRID point's power is the smallest room of ALL its slots).
// Lets a day be run in two parts when the program is replaced mid-day.
DayMoney bat_simulate_program_range(const PlanSegment* segs, int n_segs, const PlanSlot* s,
                                    int n, int from_slot, int to_slot, const PlanParams& p,
                                    float start_level_kwh);

// energikalkyl's execution loop for the plan (discharge on command).
DayMoney bat_execute_plan(const BatteryPlan* plan, const PlanSlot* s, int n,
                          const PlanParams& p, float start_level_kwh);

// ── EV ────────────────────────────────────────────────────────────────────
// Cheapest slots (ties: earlier first) whose LOCAL start hour is inside the
// availability window [win_start_h, win_end_h) (wraps midnight when
// start > end, e.g. 18-07), until kwh_needed is reached. Each slot charges
// at fuse_goe_amps(room_kw[i]) (0 = no room → skipped), except the last
// one, which gets only the amps the remaining need takes (≥ GOE_MIN_AMPS).
// amps_out[i] = 0 for unplanned slots. Returns the planned kWh.
float ev_plan_day(const float* buy_cost, const int* local_start_min, const float* room_kw,
                  int n, float slot_h, int win_start_h, int win_end_h, float kwh_needed,
                  uint8_t* amps_out);

// ── Battery + EV sharing one fuse budget ─────────────────────────────────
// One day, both loads: the EV must get ev_kwh inside its window (a cost to
// minimise), the battery cycle is optional profit. Per order:
//   battery first: bat_plan_day / bat_plan_program on the full room, then
//                  ev_plan_day in what the GRID segments leave (the Deye
//                  charges at bat_charge_kw anywhere inside a GRID segment)
//   EV first:      ev_plan_day on the full room, then the battery plan in
//                  what the EV leaves
// EV behind the Deye CT (ct_sees_ev, default DEYE_CT_SEES_GOE): the Deye
// self-consumes against house + EV, so the battery plan must see the EV:
//   EV first:      the battery plan's load includes the EV plan per slot
//   battery first: pass 1 as above (EV unknown, full room), EV plan in what
//                  the GRID segments leave, then pass 2 re-plans the battery
//                  with the EV in the load; its grid room in an EV slot is
//                  bat_charge_kw if the EV leaves that much, else 0 (the
//                  runtime gives the battery bat_charge_kw first, so a
//                  smaller GRID power there would starve the EV)
// The planner then discharges into an EV slot only where that is worth it
// (expensive slot) and bat_plan_program HOLDs elsewhere; the least-loss
// merges see the EV through bat_simulate_program. ct_sees_ev = false: the
// load excludes the EV, SELF segments never serve it (previous behaviour).
// Money (SEK, firmware conventions): ev_cost = Σ EV kWh × buy cost (the
// last, most expensive slot only counted up to ev_kwh); bat_value = Deye
// model net (bat_simulate_program) + end level × the program's terminal
// value (½ × eff × cheapest buy cost of the remaining day);
// total = ev_cost − bat_value. AUTO plans both orders and keeps the one with
// the smaller EV shortfall (> 0.05 kWh), then the smaller total; a total
// within 0.005 SEK is a tie → battery first. ev_kwh ≤ 0 (no car / no
// demand): battery first, the battery gets the full room.
struct SharedDayInput {
    int   n            = 0;        // price slots (≤ MAX_SLOTS)
    int   group        = 1;        // price slots per planning slot
    float slot_h_price = 1.0f;     // hours per price slot
    const float* buy_cost        = nullptr;  // per price slot, SEK/kWh
    const float* export_value    = nullptr;  // per price slot (nullptr = 0)
    const int*   local_start_min = nullptr;  // per price slot
    const float* load_kwh  = nullptr;        // per planning slot: expected house
                                             // load (energy the battery can serve)
    // House load to RESERVE on the fuse, per planning slot (nullptr = load_kwh).
    // Separate from load_kwh because an expected AVERAGE load is not a safe
    // fuse reserve: the pipeline passes max(expected load, BASE_LOAD_KW).
    const float* fuse_load_kwh = nullptr;
    const float* solar_kwh = nullptr;        // per planning slot (nullptr = 0)
    float grid_max_kw   = 0.0f;    // allowed grid draw (fuse budget + base load)
    float bat_charge_kw = 0.0f;    // battery grid-charge limit
    int   from_slot     = 0;       // price slot; earlier slots stay empty
    float start_level_kwh = 0.0f;
    int   max_segments  = MAX_PROG_SEGMENTS;
    PlanParams pp;                 // slot_h is set from slot_h_price × group
    int   ev_win_start_h = plant().ev_window_start_h;
    int   ev_win_end_h   = plant().ev_window_end_h;
    float ev_kwh         = 0.0f;   // EV energy needed in the window
    bool  ct_sees_ev     = DEYE_CT_SEES_GOE;   // go-e behind the Deye grid CT
};

struct SharedDayPlan {
    bool  ev_first  = false;           // order chosen
    bool  compared  = false;           // both orders evaluated (AUTO)
    float other_total_sek = 0.0f;      // total of the order NOT chosen
    int   m = 0;                       // planning slots
    PlanSlot    ps[PLAN_MAX_SLOTS];    // planning slots incl. grid room
    BatteryPlan plan;
    PlanSegment segs[PLAN_MAX_SLOTS];
    int   n_segs = 0;
    DayMoney bat;                      // expected battery money (Deye model)
    float bat_value_sek = 0.0f;
    uint8_t ev_amps[MAX_SLOTS] = {};   // per price slot
    float ev_e_kwh[MAX_SLOTS] = {};    // expected EV kWh per price slot (the
                                       // overshoot of the most expensive chosen
                                       // slot removed: Σ = min(planned, need))
    bool  ct_sees_ev = false;          // EV energy is inside ps[].load_kwh
    float ev_kwh = 0.0f;               // planned (may overshoot by one slot)
    float ev_short_kwh = 0.0f;
    float ev_cost_sek = 0.0f;
    float total_sek = 0.0f;            // ev_cost − bat_value (lower = better)
};

void plan_shared_day(const SharedDayInput& in, EvPriorityMode mode, SharedDayPlan* out);

// ── Solar model ───────────────────────────────────────────────────────────
// Expected PV kWh in [start_min, start_min + dur_min) local time on a day of
// `month`: monthly kWh/kWp (Stockholm, south ~35°) × kwp × perf_ratio / days
// in month, spread over daylight with a cos³ shape sampled per quarter hour
// (energikalkyl solar.py get_solar_production). Clock hours = local time.
float solar_model_kwh(int month, int start_min, int dur_min, float kwp, float perf_ratio);
