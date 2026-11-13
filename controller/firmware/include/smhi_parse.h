#pragma once
// Parse an SMHI point forecast reply (pure — unit-tested natively,
// test/test_smhi). No hardware, no logging.
//
// Service: SMHI open data, category snow1g version 1, point forecast:
//   https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/
//       geotype/point/lon/<lon>/lat/<lat>/data.json
//       ?parameters=air_temperature&timeseries=48
// (the older pmp3g address no longer exists). With those two query options
// the reply is under 6 KB instead of 69 KB (7 KB with timeseries=60, as in
// the test fixture):
//   {"createdTime":"…","referenceTime":"…","geometry":{…},
//    "timeSeries":[{"time":"2026-11-13T12:00:00Z",
//                   "intervalParametersStartTime":"2026-11-13T11:00:00Z",
//                   "data":{"air_temperature":2.0}}, …]}
// Times are UTC; the first 60 entries are one hour apart (48 are requested).

#include <ctime>
#include "time_local.h"

struct SmhiPoint {
    time_t utc    = 0;      // valid time of the value
    float  temp_c = 0.0f;   // air temperature, °C
};

constexpr int SMHI_MAX_POINTS = 96;

// Extract the (time, air_temperature) points of a reply, in document order.
// Entries without a plausible temperature are skipped. Returns the number of
// points (≤ max_points); 0 if the document is not a forecast reply.
int smhi_parse_points(const char* json, SmhiPoint* out, int max_points);

// Outdoor temperature for every slot of a day: the forecast at the slot's
// midpoint, interpolated between the two nearest points. A slot gets NAN
// (the caller then uses the month's normal temperature) when the forecast
// does not reach it: more than 90 minutes before the first / after the last
// point, or inside a gap of more than 6.5 hours.
// Returns the number of slots that got a temperature (0 = nothing usable).
int smhi_parse_temps(const char* json, const DaySlotClock* clk,
                     float* temp_c_out, int max_slots);

// "YYYY-MM-DDTHH:MM:SSZ" → UTC seconds since 1970. False if malformed.
bool smhi_parse_utc(const char* s, time_t* out);
