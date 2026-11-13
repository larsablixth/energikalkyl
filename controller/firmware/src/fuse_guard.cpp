/**
 * @file fuse_guard.cpp
 * @brief Fast-acting fuse protection using per-phase meter data
 *
 * Runs every FUSE_GUARD_POLL_MS (5 s) and sheds NORVI-controlled loads when
 * the most loaded phase approaches the main fuse's SUSTAINED limit (nominal
 * In, temperature-derated downwards only — never the IEC 60269 Inf headroom).
 *
 * The Easee charger is Tibber's responsibility — we never touch it.
 * But its current shows up in the meter reading, so it is accounted for.
 *
 * Shedding (thresholds in config.h, % of the sustained limit):
 *   ≥85%: level 1 — reduce go-e amps (proportionally, down to GOE_MIN_AMPS)
 *   ≥92%: level 2 — also pause battery grid-charge (Deye TOU off)
 *   ≥98%: level 3 — also pause go-e and shed the pool heat pump
 *   ≥110% (single reading): straight to level 3
 * Levels 1-3 must be seen on FUSE_ESCALATE_CONFIRM_READINGS consecutive
 * valid readings (filters motor inrush spikes).
 *
 * Recovery: one level down after the load has been below FUSE_RESTORE_PCT
 * continuously for FUSE_RESTORE_HOLD_MS; the timer restarts after each step.
 * Battery RESUME writes are additionally rate-limited
 * (FUSE_DEYE_MIN_WRITE_INTERVAL_MS) to protect the Deye EEPROM.
 *
 * Fail-safe: no valid meter reading since boot, or none for
 * FUSE_METER_STALE_MS → at least level 2 (go-e ≤ GOE_MIN_AMPS, battery paused).
 */

#include "fuse_guard.h"
#include "homewizard_p1.h"
#include "easee_client.h"
#include "fuse.h"
#include "config.h"
#include "plant.h"
#include "logger.h"
#include <cstring>
#include <cstdio>
#include <cmath>

void fuse_guard_state_init(FuseGuardState* st) {
    *st = FuseGuardState{};
    st->fuse_limit_a = fuse_effective_amps(plant().fuse_nominal_amps, false);
}

void fuse_guard_set_temperature(FuseGuardState* st, float temp_celsius) {
    /* fuse_effective_amps_temp() is clamped to ≤ nominal, so a cold
     * reading can never raise the limit above In. */
    st->fuse_limit_a = fuse_effective_amps_temp(plant().fuse_nominal_amps, temp_celsius);
}

bool fuse_guard_reading_valid(TibberPulseData* r) {
    if (!r) {
        return false;
    }
    float* cur[3] = { &r->current_l1_a, &r->current_l2_a, &r->current_l3_a };
    float max_a = 0.0f;
    for (int i = 0; i < 3; i++) {
        const float a = *cur[i];
        if (std::isnan(a) || std::isinf(a)) {
            return false;
        }
        /* Export (negative current on some meters) heats the fuse too. */
        const float abs_a = std::fabs(a);
        if (abs_a > FUSE_METER_MAX_PLAUSIBLE_A) {
            return false;
        }
        *cur[i] = abs_a;
        if (abs_a > max_a) {
            max_a = abs_a;
        }
    }
    r->max_phase_a = max_a;
    return true;
}

/* Level implied by a single reading's utilisation. */
static int level_for_util(float util_pct) {
    if (util_pct >= FUSE_HP_SHED_PCT) {
        return FUSE_SHED_HP;
    }
    if (util_pct >= FUSE_BAT_PAUSE_PCT) {
        return FUSE_SHED_BAT;
    }
    if (util_pct >= FUSE_GOE_REDUCE_PCT) {
        return FUSE_SHED_GOE;
    }
    return FUSE_SHED_NONE;
}

static constexpr int CONFIRM_N =
    (FUSE_ESCALATE_CONFIRM_READINGS < 1) ? 1 :
    (FUSE_ESCALATE_CONFIRM_READINGS > 4) ? 4 : FUSE_ESCALATE_CONFIRM_READINGS;

FuseGuardStatus fuse_guard_evaluate(FuseGuardState* st, const FuseGuardInput* in) {
    FuseGuardStatus status;
    std::memset(&status, 0, sizeof(status));
    status.fuse_limit_a = st->fuse_limit_a;

    const uint32_t now = in->now_ms;
    const bool valid = (in->meter != nullptr) && in->meter_valid;
    const int old_level = st->shed_level;
    int new_level = old_level;
    float excess_a = 0.0f;   /* amps above the go-e reduce threshold */

    if (valid) {
        st->have_good_reading = true;
        st->last_good_ms = now;
    }
    /* Wrap-safe: unsigned subtraction handles the 49-day millis() wrap. */
    const bool stale = !st->have_good_reading ||
                       static_cast<uint32_t>(now - st->last_good_ms) > FUSE_METER_STALE_MS;
    const bool limit_ok = (st->fuse_limit_a > 0.0f);

    if (valid && limit_ok) {
        status.max_phase_a = in->meter->max_phase_a;
        status.utilization_pct = status.max_phase_a / st->fuse_limit_a * 100.0f;
        excess_a = status.max_phase_a - st->fuse_limit_a * FUSE_GOE_REDUCE_PCT / 100.0f;

        /* Confirmation window: escalate only to the level that the last
         * CONFIRM_N consecutive readings all support. */
        const int reading_level = level_for_util(status.utilization_pct);
        if (st->n_recent < CONFIRM_N) {
            st->recent_levels[st->n_recent++] = reading_level;
        } else {
            for (int i = 1; i < CONFIRM_N; i++) {
                st->recent_levels[i - 1] = st->recent_levels[i];
            }
            st->recent_levels[CONFIRM_N - 1] = reading_level;
        }
        int confirmed = FUSE_SHED_NONE;
        if (st->n_recent >= CONFIRM_N) {
            confirmed = FUSE_SHED_MAX;
            for (int i = 0; i < CONFIRM_N; i++) {
                if (st->recent_levels[i] < confirmed) {
                    confirmed = st->recent_levels[i];
                }
            }
        }
        if (status.utilization_pct >= FUSE_HARD_TRIP_PCT) {
            status.hard_trip = true;
            confirmed = FUSE_SHED_MAX;
        }
        if (confirmed > new_level) {
            new_level = confirmed;
        }

        /* Restore: continuous time below FUSE_RESTORE_PCT. */
        if (status.utilization_pct < FUSE_RESTORE_PCT) {
            if (!st->below_restore) {
                st->below_restore = true;
                st->below_since_ms = now;
            } else if (new_level > FUSE_SHED_NONE &&
                       static_cast<uint32_t>(now - st->below_since_ms) >= FUSE_RESTORE_HOLD_MS) {
                new_level--;
                st->below_since_ms = now;   /* next step needs a fresh hold */
            } else {
                /* still holding */
            }
        } else {
            st->below_restore = false;
        }
    } else {
        /* No usable reading this cycle: never restore on missing data, and
         * restart the confirmation window (needs consecutive readings). */
        st->below_restore = false;
        st->n_recent = 0;
        if (!limit_ok) {
            new_level = FUSE_SHED_MAX;   /* invalid fuse config: shed all */
        }
    }

    if (stale) {
        status.meter_stale = true;
        st->below_restore = false;
        if (new_level < FUSE_SHED_BAT) {
            new_level = FUSE_SHED_BAT;
        }
    }

    /* ── go-e cap ─────────────────────────────────────────────────── */
    if (new_level >= FUSE_SHED_HP) {
        st->goe_limit_a = 0;
    } else if (new_level >= FUSE_SHED_GOE) {
        int cap;
        if (old_level == FUSE_SHED_NONE) {
            cap = (in->goe_amps > 0) ? in->goe_amps : 0;   /* start from live setpoint */
        } else if (old_level >= FUSE_SHED_HP) {
            cap = GOE_MIN_AMPS;                            /* step down from pause */
        } else {
            cap = st->goe_limit_a;
        }
        if (cap > 0 && valid && limit_ok && excess_a > 0.0f) {
            /* 3-phase go-e: 1 A less per phase ≈ 1 A less on the worst phase. */
            int reduce = static_cast<int>(std::ceil(excess_a));
            if (reduce < 1) {
                reduce = 1;
            }
            cap -= reduce;
        }
        if (stale && cap > GOE_MIN_AMPS) {
            cap = GOE_MIN_AMPS;
        }
        if (cap > 0 && cap < GOE_MIN_AMPS) {
            cap = GOE_MIN_AMPS;   /* never below IEC 61851 minimum; level 3 pauses */
        }
        if (cap > GOE_MAX_AMPS) {
            cap = GOE_MAX_AMPS;
        }
        st->goe_limit_a = cap;
    } else {
        st->goe_limit_a = 0;
    }

    /* ── battery (Deye) command with EEPROM rate limit ────────────── */
    status.bat_action = FUSE_BAT_NONE;
    const bool want_bat_paused = (new_level >= FUSE_SHED_BAT);
    if (want_bat_paused) {
        if (!st->bat_cmd_valid || !st->bat_cmd_paused) {
            status.bat_action = FUSE_BAT_PAUSE;   /* safety: never rate-limited */
            st->bat_cmd_paused = true;
            st->bat_cmd_valid = true;
            st->last_bat_cmd_ms = now;
        }
    } else if (st->bat_cmd_valid && st->bat_cmd_paused) {
        if (static_cast<uint32_t>(now - st->last_bat_cmd_ms) >= FUSE_DEYE_MIN_WRITE_INTERVAL_MS) {
            status.bat_action = FUSE_BAT_RESUME;
            st->bat_cmd_paused = false;
            st->last_bat_cmd_ms = now;
        }
        /* else: keep the battery paused until a write is allowed */
    } else {
        /* nothing to do */
    }

    st->shed_level = new_level;
    status.shed_level  = new_level;
    status.goe_reduced = (new_level >= FUSE_SHED_GOE);
    status.goe_limit_a = st->goe_limit_a;
    status.bat_paused  = st->bat_cmd_valid && st->bat_cmd_paused;
    status.hp_shed     = (new_level >= FUSE_SHED_HP);
    return status;
}

// ── Task loop (I/O through injected callbacks) ───────────────────────

static void guard_log(const FuseGuardIO* io, const char* level, const char* msg) {
    if (io->log_msg) {
        io->log_msg(level, msg);
    }
}

FuseGuardStatus fuse_guard_step(FuseGuardState* st, const FuseGuardIO* io) {
    TibberPulseData meter;
    std::memset(&meter, 0, sizeof(meter));
    bool meter_ok = io->read_meter && io->read_meter(&meter);
    if (meter_ok) {
        meter_ok = fuse_guard_reading_valid(&meter);   /* belt and braces */
    }

    FuseGuardInput in;
    in.meter = meter_ok ? &meter : nullptr;
    in.meter_valid = meter_ok;
    in.now_ms = io->now_ms ? io->now_ms() : 0;
    in.goe_amps = io->get_goe_amps ? io->get_goe_amps() : 0;
    in.battery_grid_charging = io->battery_grid_charging ? io->battery_grid_charging() : false;
    in.hp_running = io->hp_running ? io->hp_running() : false;

    const int old_level = st->shed_level;
    FuseGuardStatus status = fuse_guard_evaluate(st, &in);

    /* Publish first so the scheduler/surplus tasks respect the inhibit
     * before we touch the hardware. */
    if (io->publish) {
        io->publish(&status);
    }

    /* go-e */
    if (status.goe_reduced) {
        if (status.goe_limit_a != st->goe_cap_applied && io->set_goe_limit) {
            if (io->set_goe_limit(status.goe_limit_a)) {
                st->goe_cap_applied = status.goe_limit_a;
            } else {
                guard_log(io, "ERROR", "Fuse guard: go-e limit write failed");
            }
        }
    } else if (st->goe_cap_applied >= 0 && io->clear_goe_limit) {
        if (io->clear_goe_limit()) {
            st->goe_cap_applied = -1;
        }
    } else {
        /* no go-e change */
    }

    /* battery */
    if (status.bat_action == FUSE_BAT_PAUSE && io->pause_battery) {
        if (!io->pause_battery()) {
            st->bat_cmd_valid = false;   /* retry next cycle */
            guard_log(io, "ERROR", "Fuse guard: battery pause failed");
        }
    } else if (status.bat_action == FUSE_BAT_RESUME && io->resume_battery) {
        if (!io->resume_battery()) {
            st->bat_cmd_paused = true;   /* still paused; retry after interval */
            guard_log(io, "ERROR", "Fuse guard: battery resume failed");
        }
    } else {
        /* no battery write this cycle */
    }

    /* pool heat pump: only ever switched OFF by the guard */
    if (status.hp_shed && in.hp_running && io->set_hp) {
        io->set_hp(false);
    }

    if (status.shed_level != old_level) {
        char msg[112];
        snprintf(msg, sizeof(msg),
                 "Fuse guard: %.1fA/%.1fA (%.0f%%) shed %d->%d goe_cap=%d%s%s",
                 status.max_phase_a, status.fuse_limit_a, status.utilization_pct,
                 old_level, status.shed_level, status.goe_limit_a,
                 status.meter_stale ? " METER-STALE" : "",
                 status.hard_trip ? " HARD-TRIP" : "");
        guard_log(io, status.shed_level > old_level ? "WARN" : "INFO", msg);
    }
    return status;
}

void fuse_guard_task(void* param) {
    const FuseGuardIO* io = static_cast<const FuseGuardIO*>(param);
    if (!io) {
        return;
    }
    static FuseGuardState st;
    fuse_guard_state_init(&st);
    for (;;) {
        fuse_guard_step(&st, io);
        if (io->feed_watchdog) {
            io->feed_watchdog();
        }
        if (io->delay_ms) {
            io->delay_ms(FUSE_GUARD_POLL_MS);
        } else {
            return;   /* no delay available (test/native): single step */
        }
    }
}
