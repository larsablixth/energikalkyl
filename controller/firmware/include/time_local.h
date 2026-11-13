#pragma once
// Local time, slot ↔ wall-clock mapping and SNTP packet handling.
//
// The system clock (time()) and the DS3231 hold UTC. Local time is only ever
// derived with localtime_r() under the POSIX TZ string LOCAL_TZ_POSIX
// (Europe/Stockholm). Pure functions except time_local_init() (sets TZ).

#include <cstdint>
#include <ctime>

// setenv("TZ", LOCAL_TZ_POSIX) + tzset(). Call once at boot (and in tests).
void time_local_init(void);

// True if t is a plausible wall-clock time (year ≥ TIME_MIN_VALID_YEAR and
// < 2100). Before NTP/RTC the ESP32 clock starts at 1970 → invalid.
bool time_is_valid(time_t t);

// localtime_r wrapper; false if t is not valid.
bool time_to_local(time_t t, struct tm* out);

// Calendar date (local).
struct LocalDate {
    int year = 0, month = 0, day = 0;
};
bool local_date_equal(const LocalDate& a, const LocalDate& b);
LocalDate local_date_of(time_t t);              // {0,0,0} if t invalid
LocalDate local_date_add_days(const LocalDate& d, int days);

// UTC instant of local midnight starting the given date.
time_t local_midnight_utc(const LocalDate& d);

// Length of the local day in minutes: 1440, 1380 (spring forward),
// 1500 (fall back).
int local_day_minutes(const LocalDate& d);

// ── Slot clock ───────────────────────────────────────────────────────────
// A price day = n slots of slot_min starting at local midnight. Slot i starts
// at day_start_utc + i × slot_min × 60 (UTC arithmetic), so on DST days a
// 15-min day has 92 or 100 slots and every slot maps to the right local
// time. Use this instead of i × slot_min / 60 for tariff and windows.
struct DaySlotClock {
    time_t day_start_utc = 0;
    int    slot_min      = 0;
    int    n_slots       = 0;   // slots in the local day at this resolution
};

// False if slot_min does not divide the local day.
bool day_slot_clock_init(DaySlotClock* clk, const LocalDate& d, int slot_min);

// Clock for a price series of n_slots × slot_min starting at local midnight
// of d, even if the series does not exactly fill the day (never fails).
DaySlotClock day_slot_clock_for(const LocalDate& d, int slot_min, int n_slots);

time_t slot_start_utc(const DaySlotClock* clk, int slot);

// Local wall-clock start minute (0..1439) of the slot. On the fall-back day
// the repeated hour yields the same minutes twice; on the spring-forward day
// 02:00..02:59 never appears.
int slot_local_start_min(const DaySlotClock* clk, int slot);

// Local minute at which the slot ENDS (exclusive): 1440 if it ends at the
// next local midnight.
int slot_local_end_min(const DaySlotClock* clk, int slot);

// Slot containing instant now, or -1 if now is outside the day.
int slot_index_at(const DaySlotClock* clk, time_t now);

// ── SNTP (RFC 4330) ──────────────────────────────────────────────────────
constexpr int SNTP_PACKET_LEN = 48;

// Client request: LI=0, VN=4, Mode=3, everything else zero.
void sntp_build_request(uint8_t* pkt);

// Parse a server reply. Sanity checks: length ≥ 48, mode 4 (server),
// version 3..4, LI ≠ 3 (unsynchronised), stratum 1..15, non-zero transmit
// timestamp, resulting time valid (time_is_valid). Returns false otherwise.
bool sntp_parse_response(const uint8_t* pkt, int len, time_t* unix_out);
