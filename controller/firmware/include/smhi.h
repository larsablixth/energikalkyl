#pragma once
// SMHI temperature forecast for the house load model (hardware side: HTTPS
// via network.h). The reply is parsed by smhi_parse.h.

#include "time_local.h"

// Fetch SMHI's point forecast for the given location (decimal degrees;
// defaults SMHI_LAT / SMHI_LON in config.h, changeable in /settings.txt) and
// fill the outdoor temperature (°C) for each slot of the day described by clk.
// Slots the forecast does not reach get NAN. Returns false — and the caller
// plans with the month's normal temperature — if SMHI_ENABLED is false, the
// request fails (network, TLS, HTTP status) or the reply has nothing usable.
bool smhi_fetch_temps(const DaySlotClock* clk, float* temp_c_out, float lat, float lon);
