/*
 * scheduler.cpp — Battery charge scheduler (variable slot resolution)
 *
 * Decides which time slots to charge the battery based on spot prices
 * and Vattenfall grid fees. Supports 24 (hourly) or 96 (15-min) slots per
 * day, up to MAX_SLOTS — resolution is determined by the ENTSO-E price data.
 *
 * Algorithm:
 * Legacy cheapest-N API (scheduler_compute_day). The controller plans with
 * the time-ordered planner in battery_plan.h; this file provides the cost
 * table both use:
 *   total_cost = spot × SPOT_VAT_FACTOR + grid fee (transfer + energy tax)
 *
 * scheduler_compute_day:
 *   1. Cost table, 2. cheapest N slots, 3. spread / efficiency check,
 *   4. not profitable → NO cycling: only slots whose total buying cost is
 *      below zero stay selected (we are paid to consume). There is no
 *      "charge anyway" fallback.
 */

#include "scheduler.h"
#include "tariff.h"
#include "config.h"
#include "plant.h"
#include "time_local.h"
#include <cmath>
#include <cstring>
#include <ctime>
#include <algorithm>  // std::sort — C++14 replacement for C's qsort

// Static buffer for sort indices — safe because scheduler runs single-threaded
static int s_sort_indices[MAX_SLOTS];

// ── Core functions ───────────────────────────────────────────────────

int scheduler_rank_slots(const float* prices, int n_prices,
                         int slot_duration_min,
                         int year, int month, int day,
                         SlotCost* ranked_out) {
    if (n_prices <= 0 || n_prices > MAX_SLOTS) {
        return 0;
    }

    struct tm t = {};
    t.tm_year = year - 1900;
    t.tm_mon  = month - 1;
    t.tm_mday = day;
    t.tm_hour = 12;
    t.tm_isdst = -1;
    std::mktime(&t);
    const int weekday = t.tm_wday;
    const bool holiday = tariff_is_holiday(year, month, day);

    /* Slot start/end in LOCAL wall-clock minutes from the UTC slot clock
     * (time_local.h): correct on 92/100-slot DST days, unlike s × dur. */
    LocalDate d;
    d.year = year; d.month = month; d.day = day;
    const DaySlotClock clk = day_slot_clock_for(d, slot_duration_min, n_prices);

    for (int s = 0; s < n_prices; s++) {
        const int start_min = slot_local_start_min(&clk, s);
        const int end_min = slot_local_end_min(&clk, s);
        const int hour = start_min / 60;

        ranked_out[s].slot       = s;
        ranked_out[s].start_min  = start_min;
        ranked_out[s].end_min    = end_min;
        ranked_out[s].spot_price = prices[s];
        ranked_out[s].grid_fee   = tariff_grid_fee(hour, weekday, month, holiday);
        ranked_out[s].total_cost = tariff_buy_cost(prices[s], ranked_out[s].grid_fee);
    }
    return n_prices;
}

int scheduler_slots_needed(float capacity_kwh, float charge_kw,
                           float current_soc, float target_soc,
                           int slot_duration_min) {
    if (current_soc >= target_soc) {
        return 0;
    }
    const float energy_kwh = (target_soc - current_soc) * capacity_kwh / 100.0f;
    const float energy_per_slot = charge_kw * static_cast<float>(slot_duration_min) / 60.0f;
    if (energy_per_slot <= 0) {
        return 0;
    }
    return static_cast<int>(std::ceil(energy_kwh / energy_per_slot));
}

int scheduler_select_cheapest(const SlotCost* slots, int slot_count,
                              int n_select,
                              const bool* excluded,
                              int* selected_out) {
    if (n_select <= 0 || slot_count <= 0) {
        return 0;
    }
    if (slot_count > MAX_SLOTS) {
        slot_count = MAX_SLOTS;
    }

    // Build index array and sort by cost using std::sort with a lambda.
    // In C++14, std::sort is type-safe and the lambda captures 'slots' by
    // reference — no need for the global g_sort_costs pointer that qsort required.
    for (int i = 0; i < slot_count; i++) s_sort_indices[i] = i;
    std::sort(s_sort_indices, s_sort_indices + slot_count,
              [slots](int a, int b) {
                  /* Ties: earlier slot first (deterministic). */
                  if (slots[a].total_cost != slots[b].total_cost) {
                      return slots[a].total_cost < slots[b].total_cost;
                  }
                  return a < b;
              });

    int n = 0;
    for (int i = 0; i < slot_count && n < n_select; i++) {
        const int idx = s_sort_indices[i];
        if (excluded && excluded[idx]) {
            continue;
        }
        selected_out[n++] = idx;
    }
    return n;
}

void scheduler_compute_day(const float* prices, int n_prices,
                           int slot_duration_min,
                           int year, int month, int day,
                           int slots_needed, DaySchedule* out) {
    *out = DaySchedule{};
    if (n_prices <= 0 || n_prices > MAX_SLOTS) {
        return;
    }

    out->slot_count = n_prices;
    out->slot_duration_min = slot_duration_min;

    /* Step 1: Build cost table */
    scheduler_rank_slots(prices, n_prices, slot_duration_min,
                         year, month, day, out->costs);

    /* Step 2: Select cheapest slots for charging */
    static int charge_slots[MAX_SLOTS];
    out->n_charge_slots = scheduler_select_cheapest(
        out->costs, n_prices, slots_needed, nullptr, charge_slots);

    /* Mark charge slots in the boolean array */
    for (int i = 0; i < out->n_charge_slots; i++) {
        out->charge[charge_slots[i]] = true;
    }

    /* Step 3: Compute average costs and spread */
    float charge_sum = 0, discharge_sum = 0;
    int discharge_count = 0;
    for (int i = 0; i < out->n_charge_slots; i++) {
        charge_sum += out->costs[charge_slots[i]].total_cost;
    }
    for (int s = 0; s < n_prices; s++) {
        if (!out->charge[s]) {
            discharge_sum += out->costs[s].total_cost;
            discharge_count++;
        }
    }
    out->avg_charge_cost = (out->n_charge_slots > 0)
        ? charge_sum / static_cast<float>(out->n_charge_slots) : 0;
    out->avg_discharge_cost = (discharge_count > 0)
        ? discharge_sum / static_cast<float>(discharge_count) : 0;
    out->spread = out->avg_discharge_cost - out->avg_charge_cost;

    /* Step 4: Check profitability */
    const float break_even = out->avg_charge_cost / plant().battery_efficiency;
    const bool profitable = (out->avg_discharge_cost > break_even)
                         && (out->spread >= plant().min_spread_sek);
    out->used_fallback = !profitable;

    /* Step 5: not profitable → drop every slot that is not paid-to-consume
     * (total buying cost < 0). Never charge just because the slot is the
     * day's cheapest. */
    if (!profitable) {
        int kept = 0;
        for (int s = 0; s < n_prices; s++) {
            if (out->charge[s] && !(out->costs[s].total_cost < 0.0f)) {
                out->charge[s] = false;
            }
            if (out->charge[s]) kept++;
        }
        out->n_charge_slots = kept;
    }
}

int scheduler_day_buy_costs(const float* prices, int n_prices, int slot_duration_min,
                            int year, int month, int day, float* costs_out) {
    if (n_prices <= 0 || n_prices > MAX_SLOTS) {
        return 0;
    }
    struct tm t = {};
    t.tm_year = year - 1900;
    t.tm_mon  = month - 1;
    t.tm_mday = day;
    t.tm_hour = 12;
    t.tm_isdst = -1;
    std::mktime(&t);
    const bool holiday = tariff_is_holiday(year, month, day);
    LocalDate d;
    d.year = year; d.month = month; d.day = day;
    const DaySlotClock clk = day_slot_clock_for(d, slot_duration_min, n_prices);
    for (int s = 0; s < n_prices; s++) {
        const int hour = slot_local_start_min(&clk, s) / 60;
        costs_out[s] = tariff_buy_cost(prices[s], tariff_grid_fee(hour, t.tm_wday, month, holiday));
    }
    return n_prices;
}

// ── Legacy wrappers (24 hourly slots) ────────────────────────────────

int scheduler_rank_hours(float prices[24], int year, int month, int day,
                         HourCost ranked_out[24]) {
    return scheduler_rank_slots(prices, 24, 60, year, month, day, ranked_out);
}

int scheduler_hours_needed(float capacity_kwh, float charge_kw,
                           float current_soc, float target_soc) {
    return scheduler_slots_needed(capacity_kwh, charge_kw,
                                  current_soc, target_soc, 60);
}
