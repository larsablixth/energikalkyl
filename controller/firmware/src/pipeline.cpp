/*
 * pipeline.cpp — Daily energy scheduling pipeline (variable slot resolution)
 *
 * Daily flow on the controller (main.cpp):
 *   13:30 local  pipeline_prepare_day(tomorrow)  fetch + provisional plan,
 *                stored as TOMORROW's context (never applied to today)
 *   00:00 local  pipeline_activate_day()          tomorrow becomes today
 *   every slot   pipeline_step(today)             TOU written once per day /
 *                                                 refresh, SOC + fuse checks
 * Slot times are LOCAL wall-clock minutes from the UTC slot clock
 * (time_local.h), so 92/100-slot DST days map correctly.
 *
 * pipeline_run()/pipeline_apply_slot() are the older single-call API kept
 * for tests and sim/sil_main.cpp.
 */

#include "pipeline.h"
#include "config.h"
#include "plant.h"
#include "scheduler.h"
#include "tariff.h"
#include "fuse.h"
#include "time_local.h"
#include "battery_plan.h"
#include "house_load.h"
// C++14: use <cstring> instead of <string.h> — puts functions in std:: namespace
#include <cstring>
#include <cstdio>
#include <cmath>
#include <ctime>
#include <algorithm>

bool pipeline_run(const PipelineIO* io, PipelineResult* result) {
    // C++14: value-initialize all fields to zero/false/0.0 via {}
    *result = PipelineResult{};

    char msg[128];
    io->log_msg("INFO", "Scheduler running");

    /* Same planning as the controller (pipeline_prepare_day + pipeline_plan)
     * on a scratch context for TOMORROW. Nothing is written to the Deye or
     * the go-e here: a plan is only ever applied on its own date. */
    static PipelineDayContext ctx;
    result->prices_ok = pipeline_prepare_day(io, &ctx, io->tomorrow_year,
                                             io->tomorrow_month, io->tomorrow_day);
    if (!result->prices_ok) {
        io->show_error("Price fetch failed");
        io->log_msg("ERROR", "Keeping existing schedule");
        return false;
    }
    const int n = ctx.n_prices;
    const int dur = ctx.slot_duration_min;

    result->fuse_available = ctx.fuse_available_kw;
    result->bat_charge_kw = ctx.bat_charge_kw;
    snprintf(msg, sizeof(msg), "Fuse: %.1f kW shared budget, battery: %.1f kW (inverter max %.1f kW)",
             result->fuse_available, result->bat_charge_kw, plant().inverter_max_bat_kw);
    io->log_msg("INFO", msg);

    /* Schedule view of the plan (costs, charge flags, average spread). */
    DaySchedule* sch = &result->schedule;
    sch->slot_count = n;
    sch->slot_duration_min = dur;
    scheduler_rank_slots(ctx.prices, n, dur, ctx.year, ctx.month, ctx.day, sch->costs);
    float c_sum = 0.0f, d_sum = 0.0f;
    int c_n = 0, d_n = 0;
    for (int i = 0; i < n; i++) {
        sch->charge[i] = ctx.plan[i];
        if (ctx.plan[i]) { c_sum += sch->costs[i].total_cost; c_n++; }
        else             { d_sum += sch->costs[i].total_cost; d_n++; }
    }
    sch->n_charge_slots = c_n;
    sch->avg_charge_cost = c_n ? c_sum / static_cast<float>(c_n) : 0.0f;
    sch->avg_discharge_cost = d_n ? d_sum / static_cast<float>(d_n) : 0.0f;
    sch->spread = sch->avg_discharge_cost - sch->avg_charge_cost;
    sch->used_fallback = (c_n == 0);   /* no profitable cycle: no grid charge */

    snprintf(msg, sizeof(msg), "Battery: %d charge slots (%d min each), %d program segments, "
             "expected net %.2f SEK",
             c_n, dur, ctx.n_prog, ctx.plan_value_sek);
    io->log_msg("INFO", msg);

    /* EV plan (decoupled from the battery, shares the fuse budget). */
    int max_amps = 0;
    for (int i = 0; i < n; i++) {
        if (ctx.ev_amps[i] > 0) {
            result->ev_slots[result->n_ev_slots++] = i;
            if (ctx.ev_amps[i] > max_amps) max_amps = ctx.ev_amps[i];
        }
    }
    result->goe_amps = max_amps;
    result->ev_first = ctx.ev_first;
    result->ev_target_soc = EV_TARGET_SOC;

    char l2[22], l3[22];
    snprintf(l2, sizeof(l2), "BAT %d×%dm %.0fkr", c_n, dur, ctx.plan_value_sek);
    snprintf(l3, sizeof(l3), "EV  %d×%dm %dA", result->n_ev_slots, dur, result->goe_amps);
    io->show_status("Sched: OK", l2, l3, "");
    io->log_msg("INFO", "Scheduler complete");
    return true;
}

void pipeline_apply_slot(const PipelineIO* io, const PipelineResult* result,
                         int slot, PipelineSlotStatus* status_out) {
    const int sc = result->schedule.slot_count;
    if (slot < 0 || slot >= sc) {
        return;
    }

    char msg[128];
    bool charging = result->schedule.charge[slot];
    const int start_min = result->schedule.costs[slot].start_min;
    const int end_min = result->schedule.costs[slot].end_min;

    /* Read battery SOC before applying command */
    float battery_soc = 0.0f;
    io->read_battery_soc(&battery_soc);

    /* Apply charge/idle command to Deye */
    if (charging) {
        io->set_charge(start_min, end_min, plant().battery_max_soc);
    } else {
        io->set_idle();
    }

    /* Read real-time power status */
    PipelinePowerStatus power = {};
    bool has_power = false;
    if (io->read_power_status) {
        has_power = io->read_power_status(&power);
    }

    float grid_amps = 0.0f;
    const float fuse_max_amps = fuse_effective_amps(plant().fuse_nominal_amps, FUSE_USE_HEADROOM);
    float fuse_headroom_pct = 100.0f;
    bool fuse_limited = false;

    if (has_power) {
        /* Use per-phase data from Tibber Pulse if available (most accurate).
         * Otherwise estimate from total power / 3 phases (assumes balanced). */
        if (power.has_per_phase && power.max_phase_a > 0) {
            grid_amps = power.max_phase_a;  /* worst phase, no derating needed */
        } else if (power.grid_power_w > 0) {
            grid_amps = power.grid_power_w / (static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE);
        } else {
            /* No power data to estimate amps */
        }
        const float used_pct = (grid_amps / fuse_max_amps) * 100.0f;
        fuse_headroom_pct = 100.0f - used_pct;

        if (charging && fuse_headroom_pct < 10.0f) {
            snprintf(msg, sizeof(msg),
                     "Slot %d (%02d:%02d): FUSE WARNING %.1fA/%.1fA, reducing to idle",
                     slot, start_min/60, start_min%60, grid_amps, fuse_max_amps);
            io->log_msg("WARN", msg);
            io->set_idle();
            charging = false;
            fuse_limited = true;
        }
    }

    if (has_power) {
        snprintf(msg, sizeof(msg), "Slot %d (%02d:%02d-%02d:%02d): %s (%.2f SEK) grid=%.0fW %.1fA/ph",
                 slot, start_min/60, start_min%60, end_min/60, end_min%60,
                 charging ? "CHARGE" : "idle",
                 result->schedule.costs[slot].total_cost,
                 power.grid_power_w, grid_amps);
    } else {
        snprintf(msg, sizeof(msg), "Slot %d (%02d:%02d-%02d:%02d): %s (%.2f SEK/kWh)",
                 slot, start_min/60, start_min%60, end_min/60, end_min%60,
                 charging ? "CHARGE" : "idle",
                 result->schedule.costs[slot].total_cost);
    }
    io->log_msg("INFO", msg);

    if (status_out) {
        status_out->slot = slot;
        status_out->start_min = start_min;
        status_out->charging = charging;
        status_out->battery_soc = battery_soc;
        status_out->battery_power_w = charging ? result->bat_charge_kw * 1000.0f : 0.0f;
        status_out->grid_power_w = power.grid_power_w;
        status_out->grid_amps_per_phase = grid_amps;
        status_out->load_power_w = power.load_power_w;
        status_out->pv_power_w = power.pv_power_w;
        status_out->fuse_headroom_pct = fuse_headroom_pct;
        status_out->fuse_limited = fuse_limited;
    }
}

// ── Slot clock for a day context ─────────────────────────────────────

DaySlotClock pipeline_day_clock(const PipelineDayContext* ctx) {
    LocalDate d;
    d.year = ctx->year; d.month = ctx->month; d.day = ctx->day;
    return day_slot_clock_for(d, ctx->slot_duration_min, ctx->n_prices);
}

// ── Forecast and costs ───────────────────────────────────────────────

int pipeline_plan_group(int n_prices) {
    return (n_prices <= PLAN_MAX_SLOTS) ? 1 : (n_prices + PLAN_MAX_SLOTS - 1) / PLAN_MAX_SLOTS;
}

void pipeline_fill_forecast(const PipelineIO* io, PipelineDayContext* ctx) {
    const int n = ctx->n_prices;
    ctx->fc_load_source = FC_LOAD_NONE;
    ctx->fc_load_day_kwh = 0.0f;
    ctx->fc_temp_mean_c = 0.0f;
    ctx->fc_house_fit = HOUSE_FIT_PRIOR;
    ctx->fc_load_factor = 1.0f;
    if (n <= 0 || ctx->slot_duration_min <= 0) {
        ctx->fc_valid = false;
        return;
    }
    const DaySlotClock clk = pipeline_day_clock(ctx);
    static float buf[MAX_SLOTS];          /* one scratch buffer, reused */
    const float slot_h = static_cast<float>(ctx->slot_duration_min) / 60.0f;
    const int g = pipeline_plan_group(n);
    for (int q = 0; q < PLAN_MAX_SLOTS; q++) {
        ctx->fc_solar_kwh[q] = 0.0f;
        ctx->fc_load_kwh[q] = 0.0f;
    }

    /* ── Solar: callback, else the cos³ monthly model ─────────────────── */
    {
        const bool have = io && io->forecast_solar_kwh &&
                          io->forecast_solar_kwh(&clk, ctx->month, buf);
        for (int i = 0; i < n; i++) {
            const float v = have
                ? buf[i]
                : solar_model_kwh(ctx->month, slot_local_start_min(&clk, i),
                                  ctx->slot_duration_min, plant().solar_kwp, SOLAR_PERFORMANCE_RATIO);
            const int q = i / g;
            if (q < PLAN_MAX_SLOTS && v > 0.0f) ctx->fc_solar_kwh[q] += v;
        }
    }

    /* ── House load ────────────────────────────────────────────────────
     * 1. an explicit load forecast (callback)
     * 2. the house model at the forecast outdoor temperature
     * 3. the house model at the normal temperature of the month
     * 4. the flat profile, only when the house model is switched off */
    {
        float temp_sum = 0.0f;
        int source = FC_LOAD_CALLBACK;
        const bool have_load = io && io->forecast_load_kwh &&
                               io->forecast_load_kwh(&clk, ctx->month, buf);
        if (!have_load) {
            if (HOUSE_LOAD_USE_WEATHER_MODEL) {
                const HouseLoadModel prior = house_load_default();
                const HouseLearnState* learned = io ? io->house_learn : nullptr;
                {
                    HouseLoadModel fitted;
                    ctx->fc_house_fit = house_learn_model(learned, prior, &fitted);
                }
                /* Planning margin (settings: load_plan_factor). */
                float factor = io ? io->load_plan_factor : HOUSE_LOAD_PLAN_FACTOR;
                if (!(factor >= 0.5f && factor <= 3.0f)) factor = 1.0f;
                ctx->fc_load_factor = factor;
                const float normal = house_normal_temp_c(ctx->month);
                const bool have_temp = io && io->forecast_temp_c &&
                                       io->forecast_temp_c(&clk, ctx->month, buf);
                int from_forecast = 0;
                for (int i = 0; i < n; i++) {
                    float t = normal;
                    if (have_temp && house_temp_plausible(buf[i])) {
                        t = buf[i];
                        from_forecast++;
                    }
                    temp_sum += t;
                    const int hour = (slot_local_start_min(&clk, i) / 60) % 24;
                    buf[i] = house_expected_load_kw(learned, prior, t, hour) * slot_h * factor;
                }
                /* "forecast" only if most of the day really came from it */
                source = (from_forecast * 2 > n) ? FC_LOAD_MODEL_FC_TEMP : FC_LOAD_MODEL_NORMAL;
            } else {
                for (int i = 0; i < n; i++) {
                    const int st = slot_local_start_min(&clk, i);
                    buf[i] = HOUSE_LOAD_PROFILE_KW[(st / 60) % 24] * slot_h;
                }
                source = FC_LOAD_PROFILE;
            }
        }
        float day_kwh = 0.0f;
        for (int i = 0; i < n; i++) {
            const int q = i / g;
            if (q < PLAN_MAX_SLOTS && buf[i] > 0.0f) {
                ctx->fc_load_kwh[q] += buf[i];
                day_kwh += buf[i];
            }
        }
        ctx->fc_load_source = source;
        ctx->fc_load_day_kwh = day_kwh;
        ctx->fc_temp_mean_c = temp_sum / static_cast<float>(n);
    }
    ctx->fc_valid = true;
}

void pipeline_log_load_forecast(const PipelineIO* io, const PipelineDayContext* ctx) {
    if (!io || !io->log_msg || !ctx->fc_valid) return;
    char msg[128];
    switch (ctx->fc_load_source) {
        case FC_LOAD_MODEL_FC_TEMP:
            snprintf(msg, sizeof(msg), "House load forecast: %.1f kWh (house model, %.1f C from forecast)",
                     ctx->fc_load_day_kwh, ctx->fc_temp_mean_c);
            break;
        case FC_LOAD_MODEL_NORMAL:
            snprintf(msg, sizeof(msg), "House load forecast: %.1f kWh (house model, %.1f C normal for the month — no temperature forecast)",
                     ctx->fc_load_day_kwh, ctx->fc_temp_mean_c);
            break;
        case FC_LOAD_CALLBACK:
            snprintf(msg, sizeof(msg), "House load forecast: %.1f kWh (supplied forecast)",
                     ctx->fc_load_day_kwh);
            break;
        case FC_LOAD_PROFILE:
            snprintf(msg, sizeof(msg), "House load forecast: %.1f kWh (flat profile, house model off)",
                     ctx->fc_load_day_kwh);
            break;
        default:
            return;
    }
    io->log_msg("INFO", msg);
    if (std::fabs(ctx->fc_load_factor - 1.0f) > 0.001f) {
        snprintf(msg, sizeof(msg), "House load forecast above includes the planning margin x %.2f (expected %.1f kWh)",
                 ctx->fc_load_factor, ctx->fc_load_day_kwh / ctx->fc_load_factor);
        io->log_msg("INFO", msg);
    }
    if (ctx->fc_load_source == FC_LOAD_MODEL_FC_TEMP || ctx->fc_load_source == FC_LOAD_MODEL_NORMAL) {
        io->log_msg("INFO",
            ctx->fc_house_fit == HOUSE_FIT_FULL  ? "House model: learned from measurements (base load and heat loss)" :
            ctx->fc_house_fit == HOUSE_FIT_LEVEL ? "House model: base load learned, heat loss from config.h" :
                                                   "House model: calibration in config.h (nothing learned yet)");
    }
}

float pipeline_slot_buy_cost(const PipelineDayContext* ctx, int slot) {
    if (slot < 0 || slot >= ctx->n_prices) return 0.0f;
    struct tm t = {};
    t.tm_year = ctx->year - 1900;
    t.tm_mon = ctx->month - 1;
    t.tm_mday = ctx->day;
    t.tm_hour = 12;
    t.tm_isdst = -1;
    std::mktime(&t);
    const bool holiday = tariff_is_holiday(ctx->year, ctx->month, ctx->day);
    const DaySlotClock clk = pipeline_day_clock(ctx);
    const int hour = slot_local_start_min(&clk, slot) / 60;
    return tariff_buy_cost(ctx->prices[slot], tariff_grid_fee(hour, t.tm_wday, ctx->month, holiday));
}

// ── Look-ahead plan ──────────────────────────────────────────────────

void pipeline_plan(PipelineDayContext* ctx, float current_soc, int from_slot) {
    pipeline_plan_mode(ctx, current_soc, from_slot, static_cast<EvPriorityMode>(plant().ev_priority_mode));
}

void pipeline_plan_mode(PipelineDayContext* ctx, float current_soc, int from_slot,
                        EvPriorityMode mode) {
    const int n = ctx->n_prices;
    if (n <= 0 || ctx->slot_duration_min <= 0) {
        return;
    }
    if (from_slot < 0) from_slot = 0;
    if (from_slot >= n) from_slot = n - 1;
    if (!ctx->fc_valid) {
        pipeline_fill_forecast(nullptr, ctx);    /* default models */
    }

    const int g = pipeline_plan_group(n);
    const float slot_h_price = static_cast<float>(ctx->slot_duration_min) / 60.0f;
    const float slot_h = slot_h_price * static_cast<float>(g);
    const DaySlotClock clk = pipeline_day_clock(ctx);

    /* 1. Buying cost per price slot (spot × VAT + grid fee + energy tax,
     *    local hour, DST-safe) and the fuse budget. */
    static float cost[MAX_SLOTS];
    static float exv[MAX_SLOTS];
    static int start_min[MAX_SLOTS];
    scheduler_day_buy_costs(ctx->prices, n, ctx->slot_duration_min,
                            ctx->year, ctx->month, ctx->day, cost);
    for (int i = 0; i < n; i++) {
        start_min[i] = slot_local_start_min(&clk, i);
        exv[i] = tariff_export_value(ctx->prices[i]);
    }

    float budget = ctx->fuse_available_kw;
    if (!(budget > 0.0f)) {
        budget = fuse_available_charge_kw(plant().fuse_nominal_amps, FUSE_PHASES, FUSE_VOLTAGE,
                                          plant().fuse_phase_derating, plant().base_load_kw, FUSE_USE_HEADROOM);
    }

    /* 2. Battery plan + EV plan sharing the budget (plan_shared_day: fixed
     *    order, or AUTO = both orders, the cheaper day wins). fuse_available
     *    = grid max − BASE_LOAD_KW. Per slot the house keeps a fuse reserve
     *    of max(expected load, BASE_LOAD_KW): a forecast above the reserve
     *    (cold day, heat pump + electric heater) takes room away from
     *    charging, but a forecast below it never hands the reserve to the
     *    chargers — an expected average load says nothing about peaks. */
    static float fuse_load[PLAN_MAX_SLOTS];
    for (int q = 0; q < PLAN_MAX_SLOTS; q++) {
        const float reserve_kwh = plant().base_load_kw * slot_h;
        fuse_load[q] = (ctx->fc_load_kwh[q] > reserve_kwh) ? ctx->fc_load_kwh[q] : reserve_kwh;
    }
    SharedDayInput in;
    in.n = n;
    in.group = g;
    in.slot_h_price = slot_h_price;
    in.buy_cost = cost;
    in.export_value = exv;
    in.local_start_min = start_min;
    in.load_kwh = ctx->fc_load_kwh;
    in.fuse_load_kwh = fuse_load;
    in.solar_kwh = ctx->fc_solar_kwh;
    in.grid_max_kw = budget + plant().base_load_kw;
    in.bat_charge_kw = ctx->bat_charge_kw;
    in.from_slot = from_slot;
    in.max_segments = MAX_PROG_SEGMENTS;
    in.start_level_kwh = std::max(0.0f, (current_soc / 100.0f - in.pp.min_soc) * in.pp.capacity_kwh);
    in.ev_kwh = ctx->ev_absent ? 0.0f : plant().ev_daily_kwh;
    in.pp.end = ctx->end;        /* tomorrow's value of carried energy, if known */
    static SharedDayPlan sp;
    plan_shared_day(in, mode, &sp);

    /* Looking ahead: how much better is this plan than the one a single-day
     * view gives? (Both programs valued the same way, with tomorrow in view.) */
    ctx->lookahead_gain_sek = 0.0f;
    ctx->end_reserved_kwh = sp.plan.end_reserved_kwh;
    if (ctx->end.n > 0) {
        static SharedDayPlan sp_single;
        SharedDayInput in_single = in;
        in_single.pp.end = PlanEnd{};
        plan_shared_day(in_single, mode, &sp_single);
        PlanParams ppv = in.pp;
        ppv.slot_h = slot_h;
        const int fp = from_slot / g;
        ctx->lookahead_gain_sek =
            bat_program_objective(sp.segs, sp.n_segs, sp.ps, sp.m, fp, ppv, in.start_level_kwh) -
            bat_program_objective(sp_single.segs, sp_single.n_segs, sp.ps, sp.m, fp, ppv,
                                  in.start_level_kwh);
    }

    const int m = sp.m;
    const int ns = sp.n_segs;
    const PlanSegment* segs = sp.segs;
    const int from_p = from_slot / g;
    ctx->plan_value_sek = sp.bat.net();
    for (int i = 0; i < n; i++) ctx->ev_amps[i] = sp.ev_amps[i];
    ctx->ev_planned_kwh = sp.ev_kwh;
    ctx->ev_cost_sek = sp.ev_cost_sek;
    ctx->ev_first = sp.ev_first;
    ctx->ev_order_compared = sp.compared;
    ctx->ev_order_gain_sek = sp.compared ? sp.other_total_sek - sp.total_sek : 0.0f;

    /* 3. Segments → ctx->plan[] (Deye may grid-charge) and program points
     *    in local minutes. On the fall-back day a boundary inside the
     *    repeated hour can map to an earlier minute: dropped (the previous
     *    segment continues). */
    for (int i = from_slot; i < n; i++) {
        const int q = i / g;
        int k = 0;
        while (k + 1 < ns && segs[k + 1].start_slot <= q) k++;
        ctx->plan[i] = ns > 0 && segs[k].grid_charge;
    }
    ctx->n_prog = 0;
    for (int k = 0; k < ns && k < MAX_PROG_SEGMENTS; k++) {
        const int first = segs[k].start_slot * g;
        const int st = (k == 0) ? 0 : slot_local_start_min(&clk, first);
        if (ctx->n_prog > 0 && st <= ctx->prog[ctx->n_prog - 1].start_min) continue;
        ProgSegment p;
        p.start_min = st;
        p.grid_charge = segs[k].grid_charge;
        p.soc = segs[k].soc_pct;
        p.power_w = 0;
        if (p.grid_charge) {
            /* one power for the whole point: the smallest room of its
             * slots (fuse-safe everywhere; the program is written once) */
            const float pw = std::min(ctx->bat_charge_kw,
                bat_segment_power_kw(segs, ns, k, sp.ps, m, from_p, slot_h));
            p.power_w = static_cast<int>(std::max(0.0f, pw) * 1000.0f);
        }
        ctx->prog[ctx->n_prog++] = p;
    }

    ctx->plan_valid = true;
    ctx->plan_soc = current_soc;
    ctx->tou_written = false;  /* plan changed → program needs rewrite */
}

void pipeline_log_ev_order(const PipelineIO* io, const PipelineDayContext* ctx) {
    if (!io || !io->log_msg) return;
    char msg[128];
    if (ctx->ev_absent || !(plant().ev_daily_kwh > 0.0f)) {
        snprintf(msg, sizeof(msg), "EV/battery order: no EV demand, battery gets the full budget");
    } else if (ctx->ev_order_compared) {
        snprintf(msg, sizeof(msg), "EV/battery order: %s (auto, %.2f kr better than %s), "
                 "EV %.1f kWh %.2f kr, battery %.2f kr",
                 ctx->ev_first ? "EV first" : "battery first", ctx->ev_order_gain_sek,
                 ctx->ev_first ? "battery first" : "EV first",
                 ctx->ev_planned_kwh, ctx->ev_cost_sek, ctx->plan_value_sek);
    } else {
        snprintf(msg, sizeof(msg), "EV/battery order: %s (fixed), EV %.1f kWh %.2f kr, battery %.2f kr",
                 ctx->ev_first ? "EV first" : "battery first",
                 ctx->ev_planned_kwh, ctx->ev_cost_sek, ctx->plan_value_sek);
    }
    io->log_msg("INFO", msg);
}

// ── Extract contiguous charge windows from plan[] ───────────────────

// Count contiguous charge blocks in plan from from_slot onwards
static int count_charge_blocks(const bool* plan, int n_slots, int from_slot) {
    int blocks = 0;
    bool in_block = false;
    for (int i = from_slot; i < n_slots; i++) {
        if (plan[i] && !in_block) {
            blocks++;
            in_block = true;
        }
        if (!plan[i]) {
            in_block = false;
        }
    }
    return blocks;
}

int pipeline_plan_to_windows(const PipelineDayContext* ctx, int from_slot,
                             TouWindow* windows, int max_windows,
                             int target_soc, int charge_power_w) {
    const DaySlotClock clk = pipeline_day_clock(ctx);
    const bool* plan = ctx->plan;
    const int n_slots = ctx->n_prices;
    int nw = 0;
    int i = (from_slot > 0) ? from_slot : 0;
    while (i < n_slots && nw < max_windows) {
        if (!plan[i]) {
            i++;
            continue;
        }
        int start_min = 1440;
        int end_min = 0;
        while (i < n_slots && plan[i]) {
            /* Min start / max end over the block: on the fall-back day the
             * 02:xx wall-clock hour occurs twice, so a block crossing it is
             * not monotonic in local time. The resulting window covers every
             * planned slot (possibly a little more — charging still stops at
             * the target SOC). */
            const int st = slot_local_start_min(&clk, i);
            const int e = slot_local_end_min(&clk, i);
            if (st < start_min) start_min = st;
            if (e > end_min) end_min = e;
            i++;
        }
        if (end_min <= start_min) {
            end_min = 1440;   /* defensive: never emit an inverted window */
        }
        windows[nw].start_min = start_min;
        windows[nw].end_min = end_min;
        windows[nw].target_soc = target_soc;
        windows[nw].charge_power_w = charge_power_w;
        nw++;
    }
    return nw;
}

// ── Write TOU windows to Deye (once per plan) ──────────────────────

static void pipeline_write_tou(const PipelineIO* io, PipelineDayContext* ctx,
                               int from_slot) {
    char msg[128];
    bool ok = false;

    /* Preferred: the whole day program (charge, hold and use segments). */
    if (io->set_program && ctx->n_prog > 0) {
        ok = io->set_program(ctx->prog, ctx->n_prog);
        for (int i = 0; i < ctx->n_prog; i++) {
            const ProgSegment& g = ctx->prog[i];
            snprintf(msg, sizeof(msg), "Prog%d: from %02d:%02d %s soc=%d%%",
                     i + 1, g.start_min / 60, g.start_min % 60,
                     g.grid_charge ? "GRID-CHARGE to" : "self-use, floor", g.soc);
            io->log_msg("INFO", msg);
        }
        ctx->tou_n_windows = 0;
        ctx->tou_written = ok;
        if (!ok) {
            io->log_msg("ERROR", "Program write failed — retry next slot");
        }
        return;
    }

    /* Fallback for harnesses without set_program: grid-charge windows only
     * (no HOLD floors — the battery is self-used down to BATTERY_MIN_SOC
     * outside the windows). */
    const int total_blocks = count_charge_blocks(ctx->plan, ctx->n_prices, from_slot);
    int max_target = plant().battery_min_soc;
    for (int i = 0; i < ctx->n_prog; i++) {
        if (ctx->prog[i].grid_charge && ctx->prog[i].soc > max_target) max_target = ctx->prog[i].soc;
    }
    if (ctx->n_prog == 0) max_target = plant().battery_max_soc;
    ctx->tou_n_windows = pipeline_plan_to_windows(
        ctx, from_slot, ctx->tou_windows, MAX_TOU_WINDOWS, max_target,
        static_cast<int>(ctx->bat_charge_kw * 1000.0f));

    if (ctx->tou_n_windows == 0) {
        ok = io->set_idle();
        io->log_msg("INFO", "TOU: no charge windows — self-use program");
    } else if (io->set_charge_windows) {
        ok = io->set_charge_windows(ctx->tou_windows, ctx->tou_n_windows);
        for (int i = 0; i < ctx->tou_n_windows; i++) {
            snprintf(msg, sizeof(msg), "TOU%d: %02d:%02d-%02d:%02d target=%d%%",
                     i + 1,
                     ctx->tou_windows[i].start_min / 60,
                     ctx->tou_windows[i].start_min % 60,
                     ctx->tou_windows[i].end_min / 60,
                     ctx->tou_windows[i].end_min % 60,
                     ctx->tou_windows[i].target_soc);
            io->log_msg("INFO", msg);
        }
    } else {
        ok = io->set_charge(ctx->tou_windows[0].start_min,
                            ctx->tou_windows[0].end_min,
                            ctx->tou_windows[0].target_soc);
    }

    if (total_blocks > MAX_TOU_WINDOWS) {
        snprintf(msg, sizeof(msg), "TOU: %d charge blocks, %d in EEPROM — will refresh later",
                 total_blocks, ctx->tou_n_windows);
        io->log_msg("INFO", msg);
    }
    ctx->tou_written = ok;
    if (!ok) {
        io->log_msg("ERROR", "TOU: program write failed — retry next slot");
    }
}

// Check if TOU windows need a refresh (>3 blocks and current ones expired)
static bool tou_needs_refresh(const PipelineDayContext* ctx, int current_slot) {
    if (!ctx->tou_written || ctx->tou_n_windows == 0) {
        return false;
    }
    const DaySlotClock clk = pipeline_day_clock(ctx);
    const int current_min = slot_local_start_min(&clk, current_slot);
    /* All current TOU windows have ended? */
    bool all_expired = true;
    for (int i = 0; i < ctx->tou_n_windows; i++) {
        if (current_min < ctx->tou_windows[i].end_min) {
            all_expired = false;
            break;
        }
    }
    if (!all_expired) {
        return false;
    }
    /* Check if there are more charge slots in the future */
    for (int i = current_slot; i < ctx->n_prices; i++) {
        if (ctx->plan[i]) {
            return true;
        }
    }
    return false;
}

// ── Per-slot execution (follows the plan) ────────────────────────────

void pipeline_step(const PipelineIO* io, PipelineDayContext* ctx,
                   int slot, GridRewardSignal grid_signal,
                   PipelineSlotStatus* status_out) {
    if (slot < 0 || slot >= ctx->n_prices) {
        return;
    }

    const DaySlotClock clk = pipeline_day_clock(ctx);
    const int start_min = slot_local_start_min(&clk, slot);
    const int end_min = slot_local_end_min(&clk, slot);
    char msg[128];

    /* Step 1: Read live battery SOC */
    float battery_soc = 50.0f;
    io->read_battery_soc(&battery_soc);

    /* Step 2: Follow the look-ahead plan.
     *
     * pipeline_plan() computed the optimal charge slots from all known
     * prices. We follow that plan unless:
     *   - Battery is already full (SOC >= 95%) → skip charge
     *   - Battery is empty and plan says idle but price is negative → charge
     *   - Fuse is overloaded → override to idle
     *
     * This gives clean charge/discharge windows with minimal EEPROM writes
     * (only transitions, not every slot).
     */
    const float current_cost = pipeline_slot_buy_cost(ctx, slot);   /* SEK/kWh total */
    const int slots_needed = scheduler_slots_needed(
        plant().battery_capacity_kwh, ctx->bat_charge_kw,
        battery_soc, static_cast<float>(plant().battery_max_soc), ctx->slot_duration_min);

    /* Compute the plan once at the start of the day.
     * Don't replan on SOC drift — the Deye executes TOU windows
     * autonomously and stops charging when SOC hits target.
     * Only replan if the plan was never computed. */
    /* EV plug state: a plan made while no car was plugged in gives the
     * battery the full budget; when a car is plugged in later the day is
     * replanned once (EV demand back in, order chosen again). */
    PipelineGoeStatus goe_status;
    const bool car = io->get_goe_status && io->get_goe_status(&goe_status) &&
                     goe_status.car_connected;
    if (!ctx->plan_valid) {
        ctx->ev_absent = !car;
        pipeline_plan(ctx, battery_soc, slot);
        pipeline_log_ev_order(io, ctx);
    } else if (ctx->ev_absent && car && plant().ev_daily_kwh > 0.0f) {
        ctx->ev_absent = false;
        pipeline_plan(ctx, battery_soc, slot);
        io->log_msg("INFO", "EV plugged in: day replanned");
        pipeline_log_ev_order(io, ctx);
    }

    /* Write TOU windows to Deye once after planning.
     * The Deye executes the schedule autonomously — no need to
     * toggle registers every slot, which wears the EEPROM.
     * Rewrite when: (a) first time, (b) >3 blocks and current ones expired,
     * (c) grid reward or fuse override changed the plan. */
    if (!ctx->tou_written || tou_needs_refresh(ctx, slot)) {
        pipeline_write_tou(io, ctx, slot);
    }

    bool should_charge = ctx->plan[slot];

    /* SOC hysteresis: once battery hits full, don't restart charging
     * until SOC drops significantly (below RECHARGE_THRESHOLD_SOC).
     * This prevents the 90-95% oscillation from house load drain. */
    static bool battery_was_full = false;
    static constexpr float RECHARGE_THRESHOLD_SOC = 85.0f;

    if (battery_soc >= static_cast<float>(plant().battery_max_soc)) {
        battery_was_full = true;
    }
    if (battery_soc < RECHARGE_THRESHOLD_SOC) {
        battery_was_full = false;
    }

    /* Override: battery full or recently full — don't charge */
    if (battery_was_full) {
        should_charge = false;
    }

    /* No negative-price override needed — the plan already picks the
     * cheapest N slots (including the most negative ones).  If it says
     * idle at -0.22 SEK it's because -0.50 is coming later. Trust it. */

    /* Override: Tibber grid reward signal.
     * INCREASE = grid needs more consumption → charge battery (we get paid)
     * DECREASE = grid needs less consumption → pause charging
     * These are temporary overrides — write single-slot TOU to Deye. */
    bool tou_override = false;
    if (grid_signal == GRID_REWARD_INCREASE && slots_needed > 0) {
        should_charge = true;
        tou_override = true;
    } else if (grid_signal == GRID_REWARD_DECREASE && should_charge) {
        should_charge = false;
        tou_override = true;
    } else {
        /* No grid reward override */
    }

    /* Step 3: Read fuse status and possibly override */
    PipelinePowerStatus power = {};
    const bool has_power = (io->read_power_status && io->read_power_status(&power));

    float grid_amps = 0.0f;
    const float fuse_max = fuse_effective_amps(plant().fuse_nominal_amps, FUSE_USE_HEADROOM);
    float fuse_headroom_pct = 100.0f;
    bool fuse_limited = false;

    if (has_power) {
        if (power.has_per_phase && power.max_phase_a > 0) {
            grid_amps = power.max_phase_a;
        } else if (power.grid_power_w > 0) {
            grid_amps = power.grid_power_w / (static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE);
        } else {
            /* No power data to estimate amps */
        }
        const float used_pct = (grid_amps / fuse_max) * 100.0f;
        fuse_headroom_pct = 100.0f - used_pct;

        if (should_charge && fuse_headroom_pct < 10.0f) {
            should_charge = false;
            fuse_limited = true;
            tou_override = true;
        }
    }

    /* Step 4: Only write to Deye if overriding the TOU schedule.
     * Normal operation: TOU windows handle charge/idle automatically.
     * Override: grid reward or fuse emergency needs immediate action.
     * After override, mark TOU as needing rewrite so the planned
     * windows get restored on the next non-override slot. */
    if (tou_override) {
        if (should_charge) {
            io->set_charge(start_min, end_min, plant().battery_max_soc);
        } else {
            io->set_idle();
        }
        ctx->tou_written = false;  /* restore TOU windows next slot */
    }

    /* Step 5: EV — its own plan (cheapest slots in the availability window,
     * ctx->ev_amps), decoupled from the battery plan, plus any slot whose
     * TOTAL buying cost is negative. The fuse budget is shared in the order
     * the plan chose (ctx->ev_first): battery first → the EV gets the
     * remainder after the battery's grid charge this slot; below
     * GOE_MIN_AMPS that is 0 = pause. Nothing is sent to the go-e when no
     * car is plugged in. */
    if (car && io->set_goe_amps) {
        const bool ev_should_charge = ctx->plan_valid &&
            (ctx->ev_amps[slot] > 0 || current_cost < 0.0f);
        float budget_kw = ctx->fuse_available_kw;
        if (!(budget_kw > 0.0f)) {
            budget_kw = fuse_available_charge_kw(plant().fuse_nominal_amps, FUSE_PHASES, FUSE_VOLTAGE,
                                                 plant().fuse_phase_derating, plant().base_load_kw,
                                                 FUSE_USE_HEADROOM);
        }
        int ev_amps = 0;
        if (ev_should_charge) {
            if (!ctx->ev_first) {
                const float bat_kw = should_charge ? ctx->bat_charge_kw : 0.0f;
                ev_amps = fuse_split_budget(budget_kw, bat_kw, true, FUSE_PHASES, FUSE_VOLTAGE,
                                            GOE_MIN_AMPS, GOE_MAX_AMPS).goe_amps;
            } else {
                ev_amps = fuse_goe_amps(budget_kw, FUSE_PHASES, FUSE_VOLTAGE,
                                        GOE_MIN_AMPS, GOE_MAX_AMPS);
            }
            if (ctx->ev_amps[slot] > 0 && ev_amps > ctx->ev_amps[slot]) {
                ev_amps = ctx->ev_amps[slot];    /* planned amps */
            }
            if (ctx->goe_amps > 0 && ev_amps > ctx->goe_amps) {
                ev_amps = ctx->goe_amps;         /* daily cap, if any */
            }
        }
        io->set_goe_amps(ev_amps);   /* 0 = pause */
    }

    /* Step 6: Pool heat pump — run on solar surplus
     * The pump draws 1.9 kW (8.3A × 230V). Run it when:
     *   - PV surplus (after house load) covers the full 1.9 kW, OR
     *   - Total electricity cost is negative (paid to consume)
     * This is the same logic as the heat-pump node, but in C++. */
    const float pool_hp_kw = 1.9f;
    bool pool_hp_on = false;
    if (has_power) {
        /* Pool HP runs when PV panels produce enough to cover it.
         * The panels exist to drive the pump — start as soon as
         * production reaches 1.9 kW regardless of house load. */
        float solar_kw = power.pv_power_w / 1000.0f;
        if (solar_kw >= pool_hp_kw) {
            pool_hp_on = true;
        }
    }

    /* Log */
    snprintf(msg, sizeof(msg),
             "Slot %d (%02d:%02d) SOC=%.0f%% price=%.3f need=%d %s%s%s%s",
             slot, start_min/60, start_min%60,
             battery_soc, current_cost, slots_needed,
             should_charge ? "CHARGE" : "idle",
             fuse_limited ? " (FUSE)" : "",
             grid_signal == GRID_REWARD_INCREASE ? " GRID+" :
             grid_signal == GRID_REWARD_DECREASE ? " GRID-" : "",
             pool_hp_on ? " POOL" : "");
    io->log_msg("INFO", msg);

    /* Fill status */
    if (status_out) {
        status_out->slot = slot;
        status_out->start_min = start_min;
        status_out->charging = should_charge;
        status_out->battery_soc = battery_soc;
        const float hp_power = pool_hp_on ? 1900.0f : 0.0f;
        const float total_load = power.load_power_w + hp_power;

        /* Battery charges at full inverter rate (12.5 kW from Deye).
         * Solar surplus adds on top (DC direct, up to 15 kW total).
         * No pre-computed fuse cap — the fuse guard handles overloads
         * dynamically by reading actual per-phase amps every 5 seconds. */
        const float inverter_max_w = plant().inverter_max_bat_kw * 1000.0f;
        const float bat_hw_max_w = plant().battery_charge_kw * 1000.0f;

        /* Solar serves house first, surplus goes to battery DC */
        const float solar_surplus = power.pv_power_w - total_load;
        const float bat_from_solar = (solar_surplus > 0) ? solar_surplus : 0.0f;

        /* Grid-to-battery through inverter */
        float bat_from_grid = should_charge ? inverter_max_w : 0.0f;

        /* Total into battery, capped at hardware max */
        float bat_power = bat_from_solar + bat_from_grid;
        if (bat_power > bat_hw_max_w) {
            bat_power = bat_hw_max_w;
        }
        bat_from_grid = bat_power - bat_from_solar;
        if (bat_from_grid < 0) {
            bat_from_grid = 0.0f;
        }

        /* When not charging, battery discharges to serve house load.
         * The Deye does this automatically — house runs on battery + solar,
         * grid only needed if both can't cover the load. */
        float bat_discharge = 0.0f;
        if (!should_charge && battery_soc > static_cast<float>(plant().battery_min_soc)) {
            /* Battery covers house load up to inverter max */
            const float need = total_load - power.pv_power_w;
            if (need > 0) {
                bat_discharge = (need > inverter_max_w) ? inverter_max_w : need;
            }
        }

        /* Grid = house + battery charge - solar - battery discharge */
        float computed_grid = total_load + bat_from_grid - power.pv_power_w - bat_discharge;
        const float grid_export = (computed_grid < 0) ? -computed_grid : 0.0f;
        if (computed_grid < 0) {
            computed_grid = 0.0f;
        }

        status_out->battery_power_w = should_charge ? bat_power : -bat_discharge;
        status_out->grid_power_w = grid_export > 0 ? -grid_export : computed_grid;
        status_out->grid_amps_per_phase = (computed_grid > 0)
            ? computed_grid / (static_cast<float>(FUSE_PHASES) * FUSE_VOLTAGE) : 0.0f;
        status_out->load_power_w = power.load_power_w + hp_power;
        status_out->pv_power_w = power.pv_power_w;
        status_out->fuse_headroom_pct = (fuse_max > 0 && computed_grid > 0)
            ? 100.0f - (status_out->grid_amps_per_phase / fuse_max * 100.0f) : 100.0f;
        status_out->fuse_limited = fuse_limited;
        status_out->pool_hp_on = pool_hp_on;
        status_out->grid_reward = static_cast<int>(grid_signal);
    }
}

// ── Daily flow: prepare tomorrow at 13:30, activate at midnight ─────────

bool pipeline_prepare_day(const PipelineIO* io, PipelineDayContext* ctx,
                          int year, int month, int day) {
    /* memset, not "= PipelineDayContext{}": the struct is ~10 KB and a
     * temporary would land on the 8 KB scheduler task stack. All fields
     * are POD and zero is their default. */
    std::memset(static_cast<void*>(ctx), 0, sizeof(*ctx));
    char msg[128];

    int dur = DEFAULT_SLOT_MINUTES;
    const int n = io->fetch_prices(year, month, day, ctx->prices, MAX_SLOTS, &dur);
    if (n <= 0 || dur <= 0) {
        snprintf(msg, sizeof(msg), "Prices for %04d-%02d-%02d: fetch failed", year, month, day);
        io->log_msg("ERROR", msg);
        std::memset(static_cast<void*>(ctx), 0, sizeof(*ctx));
        return false;
    }
    ctx->n_prices = n;
    ctx->slot_duration_min = dur;
    ctx->year = year;
    ctx->month = month;
    ctx->day = day;

    LocalDate d;
    d.year = year; d.month = month; d.day = day;
    DaySlotClock full;
    if (day_slot_clock_init(&full, d, dur) && full.n_slots != n) {
        snprintf(msg, sizeof(msg), "Prices: %d slots but the local day has %d (%d-min)",
                 n, full.n_slots, dur);
        io->log_msg("WARN", msg);
    }

    ctx->fuse_available_kw = fuse_available_charge_kw(
        plant().fuse_nominal_amps, FUSE_PHASES, FUSE_VOLTAGE,
        plant().fuse_phase_derating, plant().base_load_kw, FUSE_USE_HEADROOM);
    ctx->bat_charge_kw = fuse_split_budget(
        ctx->fuse_available_kw, plant().inverter_max_bat_kw, false,
        FUSE_PHASES, FUSE_VOLTAGE, GOE_MIN_AMPS, GOE_MAX_AMPS).bat_kw;
    ctx->goe_amps = fuse_split_budget(
        ctx->fuse_available_kw, 0.0f, true,
        FUSE_PHASES, FUSE_VOLTAGE, GOE_MIN_AMPS, GOE_MAX_AMPS).goe_amps;

    /* Expected solar / house load for the day (callbacks or defaults). */
    pipeline_fill_forecast(io, ctx);
    pipeline_log_load_forecast(io, ctx);

    /* Provisional plan from the current SOC (logged / displayed). It is
     * recomputed with the live SOC when the day is activated. */
    float soc = 50.0f;
    if (!io->read_battery_soc || !io->read_battery_soc(&soc)) {
        soc = 50.0f;
    }
    pipeline_plan(ctx, soc, 0);
    int n_charge = 0;
    for (int i = 0; i < n; i++) {
        if (ctx->plan[i]) n_charge++;
    }
    snprintf(msg, sizeof(msg), "Plan %04d-%02d-%02d: %d slots x %d min, %d grid-charge slots, "
             "%d segments, %.1f SEK (provisional, SOC %.0f%%)",
             year, month, day, n, dur, n_charge, ctx->n_prog, ctx->plan_value_sek, soc);
    io->log_msg("INFO", msg);
    pipeline_log_ev_order(io, ctx);
    return true;
}

// ── Looking ahead to tomorrow ────────────────────────────────────────

void pipeline_day_end_value(const PipelineDayContext* next_day, PlanEnd* out) {
    *out = PlanEnd{};
    const int n = next_day->n_prices;
    if (n <= 0 || next_day->slot_duration_min <= 0 || !next_day->fc_valid) {
        return;
    }
    const int g = pipeline_plan_group(n);
    const float slot_h = static_cast<float>(next_day->slot_duration_min) / 60.0f * static_cast<float>(g);
    const int m = std::min((n + g - 1) / g, PLAN_MAX_SLOTS);

    float budget = next_day->fuse_available_kw;
    if (!(budget > 0.0f)) {
        budget = fuse_available_charge_kw(plant().fuse_nominal_amps, FUSE_PHASES, FUSE_VOLTAGE,
                                          plant().fuse_phase_derating, plant().base_load_kw, FUSE_USE_HEADROOM);
    }
    const float grid_max = budget + plant().base_load_kw;
    const float bat_kw = (next_day->bat_charge_kw > 0.0f) ? next_day->bat_charge_kw : budget;

    /* The next day's planning slots, as pipeline_plan_mode builds them
     * (without an EV: the car's plan for that day is not known yet). */
    static PlanSlot ps[PLAN_MAX_SLOTS];
    for (int q = 0; q < m; q++) {
        float c = 0.0f, ex = 0.0f;
        int cnt = 0;
        for (int i = q * g; i < n && i < (q + 1) * g; i++) {
            c += pipeline_slot_buy_cost(next_day, i);
            ex += tariff_export_value(next_day->prices[i]);
            cnt++;
        }
        PlanSlot x;
        x.buy_cost = cnt ? c / static_cast<float>(cnt) : 0.0f;
        x.export_value = cnt ? ex / static_cast<float>(cnt) : 0.0f;
        x.load_kwh = next_day->fc_load_kwh[q];
        x.solar_kwh = next_day->fc_solar_kwh[q];
        const float reserve_kw = std::max(next_day->fc_load_kwh[q] / slot_h, plant().base_load_kw);
        x.grid_room_kwh = std::max(0.0f, std::min(bat_kw, grid_max - reserve_kw)) * slot_h;
        ps[q] = x;
    }
    PlanParams pp;
    pp.slot_h = slot_h;
    bat_end_tranches(ps, m, pp, out);
}

bool pipeline_try_lookahead(const PipelineIO* io, PipelineDayContext* today,
                            const PipelineDayContext* tomorrow, int from_slot) {
    if (!PLAN_LOOKAHEAD_ENABLED || !today || !tomorrow || today->n_prices <= 0) {
        return false;
    }
    char msg[160];
    PlanEnd end;
    pipeline_day_end_value(tomorrow, &end);
    if (end.n <= 0) {
        if (io && io->log_msg) {
            io->log_msg("INFO", "Look-ahead: energy kept for tomorrow would be worth nothing — plan unchanged");
        }
        return false;
    }
    float soc = today->plan_soc;
    if (io && io->read_battery_soc) {
        float live = 0.0f;
        if (io->read_battery_soc(&live)) soc = live;
    }

    /* Plan on a copy: today's plan is only touched if the new one wins. */
    static PipelineDayContext trial;
    trial = *today;
    trial.end = end;
    pipeline_plan(&trial, soc, from_slot);
    const bool adopt = trial.lookahead_gain_sek >= PLAN_LOOKAHEAD_MIN_GAIN_SEK;
    if (io && io->log_msg) {
        snprintf(msg, sizeof(msg),
                 "Look-ahead: kept energy worth %.2f-%.2f SEK/kWh tomorrow; new plan %+.2f SEK, keeps %.1f kWh: %s",
                 end.value[end.n - 1], end.value[0], trial.lookahead_gain_sek,
                 trial.end_reserved_kwh, adopt ? "adopted" : "plan unchanged");
        io->log_msg("INFO", msg);
    }
    if (!adopt) {
        return false;
    }
    *today = trial;                 /* plan_valid = true, tou_written = false */
    return true;
}

void pipeline_activate_day(PipelineDayContext* ctx) {
    ctx->end = PlanEnd{};        /* the day after is not known yet */
    ctx->lookahead_gain_sek = 0.0f;
    ctx->end_reserved_kwh = 0.0f;
    ctx->plan_valid = false;     /* replan from the live SOC at the first step */
    ctx->tou_written = false;    /* daily (re)write of the Deye program */
    ctx->tou_n_windows = 0;
}
