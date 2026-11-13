#pragma once

#include "config.h"

// ── Per-slot cost breakdown ─────────────────────────────────────────
// In C++14 we use plain struct instead of typedef struct {...} Name.
// The effect is identical — you can use "SlotCost" as a type name.
// The old C way (typedef) was needed because C requires "struct SlotCost"
// everywhere; C++ doesn't.
struct SlotCost {
    int   slot       = 0;      // slot index (0..slot_count-1)
    int   start_min  = 0;      // start minute of day (0..1439)
    int   end_min    = 0;      // end minute of day (exclusive, 1..1440)
    float spot_price = 0.0f;   // SEK/kWh, excl. VAT (as ENTSO-E)
    float grid_fee   = 0.0f;   // SEK/kWh, transfer fee + energy tax, incl. VAT
    float total_cost = 0.0f;   // buying cost: spot × SPOT_VAT_FACTOR + grid_fee
};

// Backward compat alias
using HourCost = SlotCost;

// ── Day schedule ────────────────────────────────────────────────────
// Variable resolution: 24 slots (hourly) or 96 (15-min); up to MAX_SLOTS.
// slot_count and slot_duration_min describe the actual resolution.
struct DaySchedule {
    SlotCost costs[MAX_SLOTS]  = {};
    bool     charge[MAX_SLOTS] = {};    // true = charge this slot
    int      slot_count        = 0;     // actual slots used (24, 96, 1440)
    int      slot_duration_min = 0;     // minutes per slot (60, 15, 1)
    int      n_charge_slots    = 0;     // count of charge slots
    float    avg_charge_cost   = 0.0f;  // average total_cost during charge
    float    avg_discharge_cost = 0.0f; // average total_cost during non-charge
    float    spread            = 0.0f;  // discharge - charge (SEK/kWh)
    bool     used_fallback     = false; // true if no profitable spread found
    // Compat alias — n_charge_hours maps to n_charge_slots
    #define n_charge_hours n_charge_slots
};

// ── Helper ──────────────────────────────────────────────────────────
static inline int slot_to_hour(int start_min) { return start_min / 60; }

// ── Functions (variable slot count) ─────────────────────────────────

// Populate costs[].total_cost for each slot. Returns slot_count.
int scheduler_rank_slots(const float* prices, int n_prices,
                         int slot_duration_min,
                         int year, int month, int day,
                         SlotCost* ranked_out);

// Buying cost per slot (tariff_buy_cost of spot + grid fee at the slot's
// LOCAL hour, DST-safe). The single source for "total cost" everywhere
// (planner, negative-price checks, surplus task). Returns n_prices.
int scheduler_day_buy_costs(const float* prices, int n_prices, int slot_duration_min,
                            int year, int month, int day, float* costs_out);

// Compute the day schedule at given resolution (legacy cheapest-N API).
// Not profitable (spread < MIN_SPREAD_SEK or below efficiency break-even)
// → used_fallback = true and only slots with total_cost < 0 stay charged.
void scheduler_compute_day(const float* prices, int n_prices,
                           int slot_duration_min,
                           int year, int month, int day,
                           int slots_needed, DaySchedule* out);

// Calculate how many slots of charging are needed.
int scheduler_slots_needed(float capacity_kwh, float charge_kw,
                           float current_soc, float target_soc,
                           int slot_duration_min);

// Select cheapest n slots, optionally skipping excluded ones. Ties in cost:
// the earlier slot is selected first (deterministic).
// Returns count of selected slots in selected_out[].
int scheduler_select_cheapest(const SlotCost* slots, int slot_count,
                              int n_select,
                              const bool* excluded,
                              int* selected_out);

// ── Legacy wrappers (24 hourly slots) ───────────────────────────────
// These call the new functions with n_prices=24, slot_duration_min=60.

int scheduler_rank_hours(float prices[24], int year, int month, int day,
                         HourCost ranked_out[24]);

int scheduler_hours_needed(float capacity_kwh, float charge_kw,
                           float current_soc, float target_soc);
