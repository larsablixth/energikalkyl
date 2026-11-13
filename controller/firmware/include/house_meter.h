#pragma once
// Measuring the house for the learning (house_learn.h): turn the
// controller's periodic power readings and the temperatures it was told
// into one finished day at a time. Pure functions (no hardware, no logging)
// — unit-tested natively (test/test_house_meter).
//
//   power readings (W, about once a minute)  ─┐
//                                             ├─→  HouseDayLog  ─→  24 hourly kWh
//   outdoor temperature per hour (forecast)  ─┘                     24 hourly °C
//                                                                    └→ house_learn_add_day()
//
// Local time (time_local.h): hours are local hours 0..23 so that habits land
// on the hour people live by. On the two daylight-saving days an hour that
// occurs twice or not at all is simply an hour with more or less coverage.

#include <ctime>
#include <cstdint>
#include "time_local.h"

// Readings further apart than this are not joined: the time between them is
// treated as "not measured" rather than guessed.
constexpr int HOUSE_METER_MAX_GAP_S = 300;
// An hour counts only if at least this much of it was measured.
constexpr int HOUSE_METER_MIN_HOUR_S = 2700;   // 45 minutes

struct HouseDayLog {
    LocalDate day;                 // local day being collected ({0,0,0} = none)
    float  wh[24]        = {};     // energy measured in each local hour, Wh
    float  covered_s[24] = {};     // seconds of each hour that were measured
    time_t last_utc      = 0;      // previous reading
    float  last_w        = 0.0f;
    bool   have_last     = false;
};

// One finished day, ready for house_learn_add_day(): NAN = not usable.
struct HouseDayResult {
    LocalDate day;
    float hour_kwh[24];
    int   valid_hours = 0;         // hours with enough coverage
};

// Add a reading. valid = false (read failed, or the reading includes
// something that is not the house, e.g. the EV charging) breaks the chain:
// nothing is counted across it.
// Returns true when the reading starts a NEW local day and a previous day
// was being collected: *finished then holds that previous day.
bool house_meter_add(HouseDayLog* log, time_t now_utc, float house_w, bool valid,
                     HouseDayResult* finished);

// The day collected so far (for tests / display); does not reset the log.
void house_meter_result(const HouseDayLog* log, HouseDayResult* out);

// ── Outdoor temperature per local hour, for the days being measured ────────
// The controller has no thermometer; it remembers the forecast it fetched
// for a day and uses it as that day's temperature when the day is finished.
// (The model is later used with forecasts too, so it is fitted against the
// same kind of temperature it will be asked about.)
constexpr int HOUSE_TEMP_DAYS = 3;   // yesterday, today, tomorrow

struct HouseTempStore {
    LocalDate day[HOUSE_TEMP_DAYS];
    float     hour_c[HOUSE_TEMP_DAYS][24];
    bool      used[HOUSE_TEMP_DAYS] = {};
};

// Remember a day's temperatures given per price slot (NAN = unknown slot).
// An hour's value is the mean of its slots. A later call for the same day
// only fills or replaces the hours it has values for (a start-up forecast
// for "today" covers the afternoon only; the hours from yesterday's 13:30
// forecast stay). The oldest day is dropped when the store is full.
void house_temp_put(HouseTempStore* st, const LocalDate& day, const DaySlotClock* clk,
                    const float* slot_temp_c);

// Temperatures of a day: fills hour_c[24] (NAN = unknown). False if the day
// is not in the store.
bool house_temp_get(const HouseTempStore* st, const LocalDate& day, float* hour_c);
