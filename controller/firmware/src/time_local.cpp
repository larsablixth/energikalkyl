/*
 * time_local.cpp — local time (Europe/Stockholm via POSIX TZ), DST-correct
 * slot ↔ wall-clock mapping, SNTP packet build/parse. No hardware access.
 */

#include "time_local.h"
#include "config.h"
#include <cstdlib>
#include <cstring>

void time_local_init(void) {
    setenv("TZ", LOCAL_TZ_POSIX, 1);
    tzset();
}

bool time_is_valid(time_t t) {
    struct tm g;
    if (gmtime_r(&t, &g) == nullptr) {
        return false;
    }
    const int year = g.tm_year + 1900;
    return year >= TIME_MIN_VALID_YEAR && year < 2100;
}

bool time_to_local(time_t t, struct tm* out) {
    if (!out || !time_is_valid(t)) {
        return false;
    }
    return localtime_r(&t, out) != nullptr;
}

bool local_date_equal(const LocalDate& a, const LocalDate& b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
}

LocalDate local_date_of(time_t t) {
    LocalDate d;
    struct tm lt;
    if (time_to_local(t, &lt)) {
        d.year = lt.tm_year + 1900;
        d.month = lt.tm_mon + 1;
        d.day = lt.tm_mday;
    }
    return d;
}

LocalDate local_date_add_days(const LocalDate& d, int days) {
    struct tm t = {};
    t.tm_year = d.year - 1900;
    t.tm_mon = d.month - 1;
    t.tm_mday = d.day + days;
    t.tm_hour = 12;                 /* noon: never inside a DST gap */
    t.tm_isdst = -1;
    std::mktime(&t);
    LocalDate r;
    r.year = t.tm_year + 1900;
    r.month = t.tm_mon + 1;
    r.day = t.tm_mday;
    return r;
}

time_t local_midnight_utc(const LocalDate& d) {
    struct tm t = {};
    t.tm_year = d.year - 1900;
    t.tm_mon = d.month - 1;
    t.tm_mday = d.day;
    t.tm_hour = 0;                  /* Stockholm DST switches at 02:00/03:00 */
    t.tm_isdst = -1;
    return std::mktime(&t);
}

int local_day_minutes(const LocalDate& d) {
    const time_t a = local_midnight_utc(d);
    const time_t b = local_midnight_utc(local_date_add_days(d, 1));
    return static_cast<int>((b - a) / 60);
}

bool day_slot_clock_init(DaySlotClock* clk, const LocalDate& d, int slot_min) {
    if (!clk || slot_min <= 0) {
        return false;
    }
    const int minutes = local_day_minutes(d);
    if (minutes <= 0 || minutes % slot_min != 0) {
        return false;
    }
    clk->day_start_utc = local_midnight_utc(d);
    clk->slot_min = slot_min;
    clk->n_slots = minutes / slot_min;
    return true;
}

DaySlotClock day_slot_clock_for(const LocalDate& d, int slot_min, int n_slots) {
    DaySlotClock clk;
    clk.day_start_utc = local_midnight_utc(d);
    clk.slot_min = (slot_min > 0) ? slot_min : 60;
    clk.n_slots = (n_slots > 0) ? n_slots : 0;
    return clk;
}

time_t slot_start_utc(const DaySlotClock* clk, int slot) {
    return clk->day_start_utc + static_cast<time_t>(slot) * clk->slot_min * 60;
}

static int local_minute_of(time_t t) {
    struct tm lt;
    if (localtime_r(&t, &lt) == nullptr) {
        return 0;
    }
    return lt.tm_hour * 60 + lt.tm_min;
}

int slot_local_start_min(const DaySlotClock* clk, int slot) {
    return local_minute_of(slot_start_utc(clk, slot));
}

int slot_local_end_min(const DaySlotClock* clk, int slot) {
    const time_t end = slot_start_utc(clk, slot + 1);
    const int m = local_minute_of(end);
    /* Ending at local midnight after the day start = end of day. */
    return (m == 0 && end > clk->day_start_utc) ? 1440 : m;
}

int slot_index_at(const DaySlotClock* clk, time_t now) {
    if (!clk || clk->slot_min <= 0 || now < clk->day_start_utc) {
        return -1;
    }
    const long idx = static_cast<long>((now - clk->day_start_utc) / (clk->slot_min * 60));
    return (idx < clk->n_slots) ? static_cast<int>(idx) : -1;
}

// ── SNTP ────────────────────────────────────────────────────────────────

/* Seconds between 1900-01-01 (NTP era 0) and 1970-01-01. */
static constexpr uint32_t NTP_UNIX_OFFSET = 2208988800UL;

void sntp_build_request(uint8_t* pkt) {
    std::memset(pkt, 0, SNTP_PACKET_LEN);
    pkt[0] = (0 << 6) | (4 << 3) | 3;   /* LI=0, VN=4, Mode=3 (client) */
}

bool sntp_parse_response(const uint8_t* pkt, int len, time_t* unix_out) {
    if (!pkt || !unix_out || len < SNTP_PACKET_LEN) {
        return false;
    }
    const int li = (pkt[0] >> 6) & 0x3;
    const int vn = (pkt[0] >> 3) & 0x7;
    const int mode = pkt[0] & 0x7;
    const int stratum = pkt[1];
    if (mode != 4 || vn < 3 || vn > 4 || li == 3 || stratum < 1 || stratum > 15) {
        return false;
    }
    /* Transmit timestamp: bytes 40..43 seconds, 44..47 fraction. */
    const uint32_t secs = (static_cast<uint32_t>(pkt[40]) << 24) |
                          (static_cast<uint32_t>(pkt[41]) << 16) |
                          (static_cast<uint32_t>(pkt[42]) << 8) |
                           static_cast<uint32_t>(pkt[43]);
    if (secs == 0) {
        return false;
    }
    /* Era 0 ends 2036-02-07; values below the offset are era 1. */
    const int64_t unix_s = (secs >= NTP_UNIX_OFFSET)
        ? static_cast<int64_t>(secs - NTP_UNIX_OFFSET)
        : static_cast<int64_t>(secs) + 4294967296LL - NTP_UNIX_OFFSET;
    const time_t t = static_cast<time_t>(unix_s);
    if (!time_is_valid(t)) {
        return false;
    }
    *unix_out = t;
    return true;
}
