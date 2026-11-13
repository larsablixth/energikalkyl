#pragma once
// Learning the house: fit the house load model (house_load.h) to measured
// consumption and outdoor temperature. Pure functions (no hardware, no
// logging) — unit-tested natively (test/test_house_learn).
//
// ONE piece of maths serves both ways of getting a house's numbers:
//   - calibration from OLD data: sim/calibrate_house.cpp feeds a user's
//     historical consumption + weather files through house_learn_add_day()
//     and prints the constants for config.h
//   - learning on the controller: the firmware feeds each finished day
//     (measured house energy per hour + outdoor temperature per hour) and
//     the plan uses the result as soon as there is enough of it
//
// What is fitted (per day, like energikalkyl fit_heating_model):
//     y = house energy of the day                      [kWh]
//     x = Σ over the day's hours of ΔT / COP(T)        [°C·h], ΔT = max(0, T_indoor − T)
//         (in deep cold, where the prior model has the electric heater
//          helping, the hour's x includes the heater's share)
//     y ≈ A + H_LOSS × x        A = 24 × base load + hot water
//   → base load (level) and heat loss H_LOSS (slope). The heat pump's COP
//     curve, its size and the hot water figure are taken from the prior
//     model: one day's total cannot tell them apart from base load / H_LOSS.
//   The temperature at which the electric heater starts depends on H_LOSS
//   itself. The calibration tool therefore repeats the fit with the fitted
//   H_LOSS as the new prior until it settles; the controller, which keeps
//   only sums and not the old days, uses the prior from config.h — exact
//   until the heater runs, approximate in the coldest hours.
// And the daily habit: how much each local hour is above or below the model
// on average (kW, zero over the day) — cooking, laundry, night-time lows.
//
// The state is small (HouseLearnState, ~130 bytes) and meant to be saved
// once a day. Old days fade with HOUSE_LEARN_MEMORY_DAYS so the fit follows
// changes to the house, but slowly enough to remember the last winter
// through a summer.

#include <cstdint>
#include "house_load.h"

constexpr uint32_t HOUSE_LEARN_VERSION = 1;

struct HouseLearnState {
    uint32_t version   = HOUSE_LEARN_VERSION;
    uint32_t days      = 0;        // days accepted so far
    float    w         = 0.0f;     // weight sum (≈ days still remembered)
    float    sx        = 0.0f;     // weighted Σ x
    float    sy        = 0.0f;     // weighted Σ y
    float    sxx       = 0.0f;     // weighted Σ x²
    float    sxy       = 0.0f;     // weighted Σ x·y
    float    hour_offset_kw[24] = {};  // habit: kW above/below the model per local hour
    uint32_t offset_days = 0;      // days in the habit average
};

// How much the data support (house_learn_model return value).
constexpr int HOUSE_FIT_PRIOR = 0;   // not enough days: the prior model unchanged
constexpr int HOUSE_FIT_LEVEL = 1;   // base load fitted; heat loss from the prior
                                     // (too little temperature variation so far)
constexpr int HOUSE_FIT_FULL  = 2;   // base load and heat loss fitted

void house_learn_reset(HouseLearnState* s);

// Add one finished local day.
//   hour_kwh[24]     measured house energy per local hour, kWh (NAN = missing)
//   hour_temp_c[24]  outdoor temperature per local hour, °C   (NAN = missing)
//   prior            model supplying COP curve / indoor temperature
//   memory_days      forgetting horizon (HOUSE_LEARN_MEMORY_DAYS); ≤ 0 = never
//                    forget (calibration from a fixed historical data set)
// Returns false (state unchanged) if the day is unusable: fewer than 20 hours
// with both values, or an implausible reading.
bool house_learn_add_day(HouseLearnState* s, const HouseLoadModel& prior,
                         const float* hour_kwh, const float* hour_temp_c,
                         float memory_days);

// The model the data support: prior with base_kw (and h_loss_kw_per_c)
// replaced where fitted. Returns HOUSE_FIT_*.
int house_learn_model(const HouseLearnState* s, const HouseLoadModel& prior,
                      HouseLoadModel* out);

// Learned habit offset for a local hour, kW (0 until HOUSE_LEARN_MIN_DAYS
// days are in the average).
float house_learn_hour_offset_kw(const HouseLearnState* s, int local_hour);

// Expected load for an hour: model(t) + habit offset, never below
// HOUSE_LOAD_MIN_KW. s may be null (= prior model, config.h offsets).
float house_expected_load_kw(const HouseLearnState* s, const HouseLoadModel& prior,
                             float t_outdoor_c, int local_hour);

// ── Saving what was learned ───────────────────────────────────────────────
// A small self-checking blob for the SD card: magic + version + the state +
// CRC-32. house_learn_deserialize() refuses anything that is cut short, has
// a wrong checksum or version, or holds values that make no sense — the
// controller then starts learning from scratch instead of trusting garbage.
constexpr int HOUSE_LEARN_BLOB_MAX = 192;

// Returns the number of bytes written, 0 if buf is too small.
int house_learn_serialize(const HouseLearnState* s, uint8_t* buf, int buf_size);
bool house_learn_deserialize(const uint8_t* buf, int len, HouseLearnState* out);

// The day's regressor x for a set of hourly temperatures (24 values, all
// valid): Σ heating electricity per unit of heat loss. Exposed for tools/tests.
float house_learn_day_x(const HouseLoadModel& prior, const float* hour_temp_c);
