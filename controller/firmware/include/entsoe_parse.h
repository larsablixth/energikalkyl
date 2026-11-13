#pragma once
// Pure ENTSO-E A44 (day-ahead prices) XML handling — no network, unit-tested
// natively (test/test_entsoe). The HTTPS fetch lives in entsoe.cpp.
//
// What the parser handles (see entsoe_parse.cpp for details):
//   - curveType A03 ("variable sized block"): a position is OMITTED when its
//     price equals the previous position's → missing positions are filled
//     forward. Position 1 of a period must be present.
//   - several TimeSeries / Periods in one document (day split across
//     periods, PT15M and PT60M duplicates of the same day): the FINEST
//     resolution present for the day is used, coarser duplicates ignored.
//   - Period times are UTC; output slot k starts at local midnight (UTC) +
//     k × resolution, i.e. 92 / 96 / 100 quarter-hours (23 / 24 / 25 hours)
//     on DST days — the same mapping as DaySlotClock (time_local.h).
//   - the number of slots comes from the local day length / resolution,
//     never from the number of <Point> elements.
//   - rejected (returns 0): truncated document (no closing root tag, an
//     unclosed Period/Point), unknown resolution, a slot of the day not
//     covered by any period of the chosen resolution, position outside its
//     period, currency other than EUR, Acknowledgement (error) document.

#include "time_local.h"

// Request window for one LOCAL day, as ENTSO-E wants it: UTC yyyyMMddHHmm.
// start = local midnight of d (UTC), end = next local midnight (UTC).
// Buffers must hold ≥ 13 chars. 2025-06-20 → "202506192200", "202506202200".
void entsoe_request_window(const LocalDate& d, char* start_out, char* end_out);

// Parse "YYYY-MM-DDTHH:MMZ" (or with seconds, "…:SSZ") as UTC. -1 on error.
long long entsoe_parse_utc(const char* s);

// Parse an A44 document for the local day d. Prices are converted
// EUR/MWh → SEK/kWh with eur_sek (excl. VAT, as published).
// Returns the number of slots written (92/96/100 for PT15M, 23/24/25 for
// PT60M), 0 if the document is rejected. *slot_min_out = resolution.
int entsoe_parse_day(const char* xml, const LocalDate& d, float eur_sek,
                     float* prices_out, int max_slots, int* slot_min_out);
