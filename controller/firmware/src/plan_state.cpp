/*
 * plan_state.cpp — pure day-rollover / fetch-retry / safe-state decisions.
 */

#include "plan_state.h"

RolloverAction plan_rollover_decide(bool today_valid, const LocalDate& today_plan,
                                    bool tomorrow_valid, const LocalDate& tomorrow_plan,
                                    const LocalDate& now) {
    if (today_valid && local_date_equal(today_plan, now)) {
        return ROLL_KEEP;
    }
    if (tomorrow_valid && local_date_equal(tomorrow_plan, now)) {
        return ROLL_SWAP;
    }
    return ROLL_NO_PLAN;
}

FetchAction fetch_retry_decide(FetchRetryState* st, const FetchRetryConfig& cfg,
                               const LocalDate& today, int now_min) {
    if (!local_date_equal(st->day, today)) {
        *st = FetchRetryState{};
        st->day = today;
        st->next_min = cfg.start_min;
    }
    if (st->succeeded || st->gave_up) {
        return FETCH_IDLE;
    }
    if (now_min < st->next_min) {
        return FETCH_IDLE;
    }
    if (now_min >= cfg.deadline_min) {
        st->gave_up = true;
        return FETCH_GIVE_UP;
    }
    return FETCH_NOW;
}

void fetch_retry_result(FetchRetryState* st, const FetchRetryConfig& cfg,
                        bool ok, int now_min) {
    st->attempts++;
    if (ok) {
        st->succeeded = true;
        return;
    }
    st->next_min = now_min + cfg.interval_min;
}

SafetyAction safety_decide(const SafetyInputs& in) {
    if (!in.time_valid) {
        return SAFETY_TIME_INVALID;
    }
    if (in.modbus_failures >= in.max_modbus_failures) {
        return SAFETY_MODBUS;
    }
    if (!in.grid_charge_programmed) {
        return SAFETY_OK;           /* nothing that could go stale */
    }
    if (in.plan_written_utc <= 0 || in.now_utc - in.plan_written_utc > in.max_plan_age_s ||
        in.now_utc < in.plan_written_utc - 3600) {   /* clock jumped back */
        return SAFETY_PLAN_STALE;
    }
    if (in.plan_expires_utc > 0 && in.now_utc >= in.plan_expires_utc) {
        return SAFETY_PLAN_EXPIRED;
    }
    return SAFETY_OK;
}

const char* safety_action_name(SafetyAction a) {
    switch (a) {
        case SAFETY_OK:           return "ok";
        case SAFETY_TIME_INVALID: return "time not valid";
        case SAFETY_MODBUS:       return "repeated Modbus failures";
        case SAFETY_PLAN_STALE:   return "plan stale (>26 h)";
        case SAFETY_PLAN_EXPIRED: return "plan expired (day over)";
        case SAFETY_NO_PLAN:      return "no plan for today";
    }
    return "?";
}

int64_t plan_expiry_utc(const LocalDate& d, int64_t grace_s) {
    return static_cast<int64_t>(local_midnight_utc(local_date_add_days(d, 1))) + grace_s;
}

bool safe_pending_next(bool pending, SafetyAction need, bool safe_program_verified,
                       bool time_valid, bool today_plan_valid) {
    if (need != SAFETY_OK) {
        return true;
    }
    if (!safe_program_verified || !time_valid || !today_plan_valid) {
        return pending;
    }
    return false;
}

bool charge_write_permitted(bool guard_bat_inhibit, bool safe_pending, bool time_valid) {
    return !guard_bat_inhibit && !safe_pending && time_valid;
}
