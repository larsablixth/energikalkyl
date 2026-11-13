/**
 * @file fuse.cpp
 * @brief DIAZED fuse power limiting for Swedish residential electrical installations
 *
 * Implements power budget calculations based on the main fuse (huvudsäkring) that
 * protects the service entrance of a Swedish residential building. These calculations
 * are SAFETY-CRITICAL: exceeding the fuse rating will trip the main breaker, cutting
 * power to the entire house.
 *
 * Swedish residential installations use DIAZED fuses (IEC 60269-2, "Neozed" in
 * some markets) with standard ratings from the DII and DIII series:
 *   - DII:  6A, 10A, 16A, 20A, 25A (max 500V)
 *   - DIII: 35A, 50A, 63A (max 500V)
 *
 * This module only supports the ratings commonly used as main fuses (16-63A).
 * Smaller ratings (6A, 10A) are for sub-circuits and not relevant here.
 *
 * The fuse rating determines:
 *   1. Maximum total power the house can draw simultaneously
 *   2. How much headroom is available for EV + battery charging
 *   3. Whether the EV charge current needs to be reduced during battery charging
 *
 * Three-phase power calculation:
 *   P_max = I_fuse x N_phases x V_phase x derating_factor
 *
 *   With typical values (25A fuse, 3-phase, 230V, 0.7 derating):
 *   P_max = 25 x 3 x 230 x 0.7 = 12,075 W = 12.08 kW
 *
 * Phase derating (0.7 default):
 *   Real loads are never perfectly balanced across phases. The derating factor
 *   accounts for worst-case phase imbalance. At 0.7, we assume one phase could
 *   carry up to 1/0.7 = 1.43x its share. This is conservative but safe.
 *   Adjust upward (toward 1.0) only if you have measured phase balance data.
 *
 * IEC 60269 headroom mode (NOT used for protection — FUSE_USE_HEADROOM=false):
 *   DIAZED gG (general-purpose, "trög") fuses have a defined non-fusing current
 *   (Inf) of 1.25 x In for 1 hour at 30C reference temperature. This means a
 *   25A fuse will NOT blow at 31.25A for up to 1 hour — and nothing more. Charge
 *   windows (1-3 h) plus EV charging are sustained loads, so protection uses In.
 *   CAUTION: Ambient temperature above 30C reduces the non-fusing threshold by
 *   approximately 6% per 10C. Do not enable headroom mode in poorly ventilated
 *   electrical cabinets or during heat waves.
 *
 * Dependencies:
 *   - config.h: FUSE_NOMINAL_AMPS, FUSE_PHASES, FUSE_VOLTAGE, FUSE_PHASE_DERATING,
 *               BASE_LOAD_KW, FUSE_USE_HEADROOM, GOE_MIN_AMPS, GOE_MAX_AMPS
 *
 * References:
 *   - IEC 60269-2: Low-voltage fuses, supplementary requirements for fuses for use
 *     by authorized persons (fuses mainly for industrial application)
 *   - SS-EN 60269-3: Swedish adoption, DIAZED and Neozed fuse-links
 *   - Elinstallationsreglerna (SS 436 40 00): Swedish wiring regulations
 */

#include "fuse.h"
#include "config.h"
#include <cmath>

/**
 * Standard DIAZED fuse ratings used as main fuses in Swedish homes (amperes).
 *
 * Only these specific ratings are physically available — you cannot buy a 30A
 * DIAZED fuse. The fuse holder (D-element) size also differs:
 *   - DII  (E27 base): 16A, 20A, 25A — most common in older Swedish houses
 *   - DIII (E33 base): 35A, 50A, 63A — newer installations, larger houses
 *
 * The grid operator (nätägare) seals the main fuse and charges an annual
 * subscription fee (abonnemangsavgift) based on its rating. Upgrading from
 * 25A to 35A can cost 5,000-15,000 SEK/year more, which is why the headroom
 * mode exists — to squeeze more power from a smaller (cheaper) fuse subscription.
 */
static const int diazed_sizes[] = { 16, 20, 25, 35, 50, 63 };
static constexpr int diazed_count = 6;

/**
 * Validate that a fuse rating matches a real DIAZED standard size.
 *
 * Rejects non-standard values to prevent misconfiguration. If someone enters
 * 30A (not a real DIAZED rating), all power calculations return 0, which is
 * a safe failure mode — no charging will be scheduled.
 *
 * @param nominal  Fuse rating in amperes to validate
 * @return true if the rating matches a standard DIAZED size
 */
static bool is_valid_diazed(int nominal) {
    for (int i = 0; i < diazed_count; i++) {
        if (diazed_sizes[i] == nominal) {
            return true;
        }
    }
    return false;
}

/**
 * Get the effective amperage for a given fuse, optionally with IEC 60269 headroom.
 *
 * Without headroom: returns the nominal rating (what's printed on the fuse).
 * With headroom: returns 1.15x the nominal rating (below the IEC 60269 Inf
 * of 1.25x). Inf only guarantees non-blow for 1 hour, so this is NOT a
 * sustained rating; the planner and fuse guard use use_headroom=false.
 *
 * Returns 0.0 for invalid fuse sizes (safe default — prevents charging).
 *
 * @param nominal_amps  Fuse rating in amperes (must be a valid DIAZED size)
 * @param use_headroom  If true, apply the 1.15x short-term factor (analysis only)
 * @return Effective amperage (0.0 if invalid fuse size)
 */
float fuse_effective_amps(int nominal_amps, bool use_headroom) {
    if (!is_valid_diazed(nominal_amps)) {
        return 0.0f;
    }
    /* Short-term headroom (analysis only, < 1 h). For sustained load use
     * nominal, or fuse_effective_amps_temp() which only derates. */
    if (use_headroom) {
        return static_cast<float>(nominal_amps) * 1.15f;
    }
    return static_cast<float>(nominal_amps);
}

/**
 * Sustained, temperature-derated fuse limit (never above nominal In).
 * See fuse.h for the formula and the sensor-fault handling.
 */
float fuse_effective_amps_temp(int nominal_amps, float temp_celsius) {
    if (!is_valid_diazed(nominal_amps)) {
        return 0.0f;
    }
    /* Temperature derating of the SUSTAINED limit (nominal In).
     * Warm fuse/cabinet → less margin before the fuse element heats up, so
     * reduce ~6% per 10°C above the 30°C reference. Below the reference we
     * do NOT add headroom: the factor is clamped to 1.0, so this function
     * can only ever return ≤ In.
     *
     * Sensor faults are treated as "warm": NaN, the DS18B20 error codes
     * (-127 = no device, 85 = power-on reset value) and anything outside the
     * sensor's -55..125°C range use FUSE_TEMP_FAULT_FACTOR. */
    float factor;
    const bool plausible = !std::isnan(temp_celsius) &&
                           temp_celsius >= -55.0f && temp_celsius <= 125.0f &&
                           temp_celsius != 85.0f;
    if (!plausible) {
        factor = FUSE_TEMP_FAULT_FACTOR;
    } else {
        factor = 1.0f - (temp_celsius - FUSE_TEMP_REF_C) * FUSE_TEMP_DERATE_PER_C;
    }
    if (factor > 1.0f) {
        factor = 1.0f;                  /* never above nominal */
    }
    if (factor < FUSE_TEMP_MIN_FACTOR) {
        factor = FUSE_TEMP_MIN_FACTOR;
    }
    return static_cast<float>(nominal_amps) * factor;
}

/**
 * Calculate the maximum total power available from the main fuse.
 *
 * Formula: P = I_effective x N_phases x V_phase x derating_factor
 *
 * Examples with 230V and 0.7 derating:
 *   25A, no headroom:  25.0  x 3 x 230 x 0.7 = 12,075 W = 12.08 kW
 *   25A, with headroom: 28.75 x 3 x 230 x 0.7 = 13,886 W (analysis only)
 *   35A, no headroom:  35.0  x 3 x 230 x 0.7 = 16,905 W = 16.91 kW
 *
 * @param nominal_amps    Main fuse rating (e.g. 25)
 * @param phases          Number of phases (1 or 3; always 3 for Swedish mains)
 * @param voltage         Phase voltage in volts (230V in Sweden, per SS-EN 50160)
 * @param phase_derating  Derating factor for phase imbalance (0.0-1.0, typically 0.7)
 * @param use_headroom    Apply 1.15x short-term headroom (keep false)
 * @return Maximum power in kilowatts (0.0 if invalid fuse size)
 */
float fuse_max_power_kw(int nominal_amps, int phases, float voltage,
                        float phase_derating, bool use_headroom) {
    const float amps = fuse_effective_amps(nominal_amps, use_headroom);
    if (amps <= 0) {
        return 0.0f;
    }
    return amps * static_cast<float>(phases) * voltage * phase_derating / 1000.0f;
}

/**
 * Calculate available power for charging after subtracting household base load.
 *
 * This is the power budget that can be split between battery charging (Deye
 * inverter) and EV charging (go-e charger). The scheduler's fuse conflict
 * resolution uses this value to determine if both can charge simultaneously
 * or if the EV target SOC needs to be reduced.
 *
 * Example with 25A fuse, 3kW base load, no headroom:
 *   Max power:     12.08 kW
 *   Base load:     -3.00 kW (lights, fridge, HVAC, standby)
 *   Available:      9.08 kW for charging
 *
 *   Battery draws: -5.00 kW (Deye at CC phase)
 *   Remaining:      4.08 kW for EV (about 5.9A per phase on 3-phase go-e)
 *
 * Returns 0.0 if base load already exceeds fuse capacity (no room for charging).
 *
 * @param fuse_amps       Main fuse rating
 * @param phases          Number of phases
 * @param voltage         Phase voltage (V)
 * @param phase_derating  Phase imbalance derating factor
 * @param base_load_kw    Estimated household base load in kW (from config.h)
 * @param use_headroom    Apply IEC 60269 headroom
 * @return Available charging power in kW (never negative)
 */
float fuse_available_charge_kw(int fuse_amps, int phases, float voltage,
                               float phase_derating, float base_load_kw,
                               bool use_headroom) {
    const float max_kw = fuse_max_power_kw(fuse_amps, phases, voltage,
                                           phase_derating, use_headroom);
    const float available = max_kw - base_load_kw;
    return (available > 0) ? available : 0.0f;
}

/**
 * Convert available power headroom into a go-e charger amperage setting.
 *
 * The go-e charger accepts a current limit in whole amperes (per phase).
 * This function converts the available kW back to amps and clamps to the
 * charger's operating range.
 *
 * The go-e Charger Gemini has specific constraints:
 *   - Minimum: 6A (IEC 61851 minimum for Mode 3 charging; below this the EVSE
 *     must stop charging entirely rather than trickle)
 *   - Maximum: 16A for the standard model (32A for go-e Charger HOMEfix)
 *
 * If the available power translates to fewer than min_amps, returns 0 (meaning
 * "do not charge the EV"). This prevents the charger from oscillating between
 * on and off states, which stresses the EV's onboard charger contactors.
 *
 * Formula: I = P(kW) x 1000 / (N_phases x V_phase)
 * Uses floor() to be conservative — always round down to stay within fuse limits.
 *
 * @param available_kw  Available power for EV charging (from fuse_available_charge_kw)
 * @param phases        Number of phases the go-e is connected to (1 or 3)
 * @param voltage       Phase voltage (230V)
 * @param min_amps      Minimum charger current (6A per IEC 61851)
 * @param max_amps      Maximum charger current (16A for go-e Gemini)
 * @return Charger current in whole amps, or 0 if insufficient power
 */
int fuse_goe_amps(float available_kw, int phases, float voltage,
                  int min_amps, int max_amps) {
    if (available_kw <= 0 || phases <= 0 || voltage <= 0) {
        return 0;
    }
    /* Convert kW to amps per phase. floor() ensures we never exceed the fuse limit
     * due to rounding — a 1A overestimate at 3x230V = 690W of unexpected load. */
    int amps = static_cast<int>(std::floor(available_kw * 1000.0f / (static_cast<float>(phases) * voltage)));
    if (amps < min_amps) {
        return 0;  /* Below IEC 61851 minimum — don't charge */
    }
    if (amps > max_amps) {
        amps = max_amps;  /* Clamp to charger hardware limit */
    }
    return amps;
}

/**
 * Split one fuse budget between battery grid-charge and EV charging.
 *
 * Both loads hang off the same main fuse, so they must come out of the same
 * budget: base load + battery + EV ≤ fuse limit (with phase derating, which
 * is already applied in available_kw). Battery first, EV gets the remainder.
 * A remainder below the IEC 61851 minimum means "pause the EV" (0), never a
 * fallback current.
 */
FuseBudgetSplit fuse_split_budget(float available_kw, float bat_request_kw,
                                  bool ev_wants_charge, int phases, float voltage,
                                  int min_amps, int max_amps) {
    FuseBudgetSplit split;
    if (!(available_kw > 0.0f)) {
        return split;  /* no budget (or NaN): nothing may charge from grid */
    }
    float bat = (bat_request_kw > 0.0f) ? bat_request_kw : 0.0f;
    if (bat > available_kw) {
        bat = available_kw;
    }
    split.bat_kw = bat;
    if (ev_wants_charge) {
        split.goe_amps = fuse_goe_amps(available_kw - bat, phases, voltage,
                                       min_amps, max_amps);
    }
    return split;
}
