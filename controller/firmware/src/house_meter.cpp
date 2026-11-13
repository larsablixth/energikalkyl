// house_meter.cpp — collect power readings and temperatures into finished
// days for the house learning (see house_meter.h)

#include "house_meter.h"
#include <cmath>

namespace {

bool local_hour_of(time_t t, LocalDate* date, int* hour, int* sec_into_hour) {
    struct tm lt;
    if (!time_to_local(t, &lt)) return false;
    date->year = lt.tm_year + 1900;
    date->month = lt.tm_mon + 1;
    date->day = lt.tm_mday;
    *hour = lt.tm_hour;
    *sec_into_hour = lt.tm_min * 60 + lt.tm_sec;
    return true;
}

void reset(HouseDayLog* log, const LocalDate& day) {
    log->day = day;
    for (int h = 0; h < 24; h++) {
        log->wh[h] = 0.0f;
        log->covered_s[h] = 0.0f;
    }
    log->have_last = false;
}

}  // namespace

void house_meter_result(const HouseDayLog* log, HouseDayResult* out) {
    out->day = log->day;
    out->valid_hours = 0;
    for (int h = 0; h < 24; h++) {
        if (log->covered_s[h] >= static_cast<float>(HOUSE_METER_MIN_HOUR_S)) {
            /* Scale to a full hour: energy per measured second × 3600. */
            out->hour_kwh[h] = log->wh[h] / 1000.0f * (3600.0f / log->covered_s[h]);
            out->valid_hours++;
        } else {
            out->hour_kwh[h] = NAN;
        }
    }
}

bool house_meter_add(HouseDayLog* log, time_t now_utc, float house_w, bool valid,
                     HouseDayResult* finished) {
    LocalDate date;
    int hour = 0, sec = 0;
    if (!local_hour_of(now_utc, &date, &hour, &sec)) {
        log->have_last = false;        /* no valid clock: count nothing */
        return false;
    }
    if (log->day.year == 0) {
        reset(log, date);
    }
    const bool usable = valid && std::isfinite(house_w) && house_w >= 0.0f;

    /* The time since the previous reading, at the average of the two powers.
     * It is at most HOUSE_METER_MAX_GAP_S long, so it touches at most two
     * hours: the one the previous reading was in and the current one. */
    double in_this_hour = 0.0, in_prev_hour = 0.0;
    float avg_w = 0.0f;
    LocalDate prev_date;
    int prev_hour = 0, prev_sec = 0;
    if (usable && log->have_last &&
        local_hour_of(log->last_utc, &prev_date, &prev_hour, &prev_sec)) {
        const double dt = difftime(now_utc, log->last_utc);
        if (dt > 0.0 && dt <= HOUSE_METER_MAX_GAP_S) {
            avg_w = 0.5f * (log->last_w + house_w);
            in_this_hour = (dt < sec) ? dt : static_cast<double>(sec);
            in_prev_hour = dt - in_this_hour;
        }
    }

    /* The earlier part belongs to the hour (and day) of the previous reading. */
    if (in_prev_hour > 0.0 && local_date_equal(prev_date, log->day)) {
        log->wh[prev_hour] += avg_w * static_cast<float>(in_prev_hour) / 3600.0f;
        log->covered_s[prev_hour] += static_cast<float>(in_prev_hour);
    }

    /* A new local day: hand the finished one over and start afresh. */
    bool day_done = false;
    if (!local_date_equal(log->day, date)) {
        if (finished) {
            house_meter_result(log, finished);
        }
        day_done = true;
        reset(log, date);
    }

    if (in_this_hour > 0.0) {
        log->wh[hour] += avg_w * static_cast<float>(in_this_hour) / 3600.0f;
        log->covered_s[hour] += static_cast<float>(in_this_hour);
    }

    if (usable) {
        log->last_utc = now_utc;
        log->last_w = house_w;
        log->have_last = true;
    } else {
        log->have_last = false;        /* nothing is counted across a bad reading */
    }
    return day_done;
}

// ── Temperature store ──────────────────────────────────────────────────────

void house_temp_put(HouseTempStore* st, const LocalDate& day, const DaySlotClock* clk,
                    const float* slot_temp_c) {
    /* Hourly means of the slots that have a value. */
    float sum[24] = {};
    int cnt[24] = {};
    bool any = false;
    for (int i = 0; i < clk->n_slots; i++) {
        const float t = slot_temp_c[i];
        if (!std::isfinite(t)) continue;
        const int h = (slot_local_start_min(clk, i) / 60) % 24;
        sum[h] += t;
        cnt[h]++;
        any = true;
    }
    if (!any) return;

    int idx = -1;
    for (int k = 0; k < HOUSE_TEMP_DAYS; k++) {
        if (st->used[k] && local_date_equal(st->day[k], day)) { idx = k; break; }
    }
    if (idx < 0) {
        for (int k = 0; k < HOUSE_TEMP_DAYS; k++) {
            if (!st->used[k]) { idx = k; break; }
        }
        if (idx < 0) {
            /* Full: replace the oldest day. */
            idx = 0;
            for (int k = 1; k < HOUSE_TEMP_DAYS; k++) {
                if (local_midnight_utc(st->day[k]) < local_midnight_utc(st->day[idx])) idx = k;
            }
        }
        st->used[idx] = true;
        st->day[idx] = day;
        for (int h = 0; h < 24; h++) st->hour_c[idx][h] = NAN;
    }
    for (int h = 0; h < 24; h++) {
        if (cnt[h] > 0) st->hour_c[idx][h] = sum[h] / static_cast<float>(cnt[h]);
    }
}

bool house_temp_get(const HouseTempStore* st, const LocalDate& day, float* hour_c) {
    for (int k = 0; k < HOUSE_TEMP_DAYS; k++) {
        if (st->used[k] && local_date_equal(st->day[k], day)) {
            for (int h = 0; h < 24; h++) hour_c[h] = st->hour_c[k][h];
            return true;
        }
    }
    for (int h = 0; h < 24; h++) hour_c[h] = NAN;
    return false;
}
