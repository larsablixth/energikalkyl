#pragma once

// Returns the Vattenfall grid fee (SEK/kWh, incl. VAT) for the given hour:
// transfer fee + energy tax (GRID_FEE_HIGH / GRID_FEE_LOW, config.h).
// weekday: 0=Sunday .. 6=Saturday (tm_wday convention)
float tariff_grid_fee(int hour, int weekday, int month, bool is_holiday);

// Returns true if the given date is a Swedish public holiday.
// Automatically computes Easter-dependent holidays for any year.
bool tariff_is_holiday(int year, int month, int day);

// Cost of BUYING 1 kWh (SEK): spot (excl. VAT) × SPOT_VAT_FACTOR + grid_fee
// (tariff_grid_fee: transfer + energy tax, incl. VAT). Same as energikalkyl
// total_ore = spot × spot_vat_factor + tariff.total_cost_ore().
float tariff_buy_cost(float spot_sek, float grid_fee_sek);

// Value of EXPORTING 1 kWh (SEK): max(0, spot × EXPORT_PRICE_FACTOR −
// EXPORT_FEE_SEK), no VAT. 0 in zero-export mode (EXPORT_PRICE_FACTOR = 0).
float tariff_export_value(float spot_sek);
