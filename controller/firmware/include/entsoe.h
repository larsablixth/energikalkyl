#pragma once

#include "config.h"

// Fetch day-ahead prices from ENTSO-E. Auto-detects resolution from XML.
// Returns number of price slots parsed (24, 96, or 1440), 0 on failure.
// slot_duration_out: set to detected resolution in minutes (60, 15, or 1).
int entsoe_fetch(const char* token, const char* domain,
                 int year, int month, int day,
                 float* prices_out, int max_slots,
                 int* slot_duration_out);
