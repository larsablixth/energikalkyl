#pragma once

// ── DIAZED Fuse Power Limiting (IEC 60269, gG/gL "trög") ─────────────────
//
// Swedish residential mains use DIAZED fuses. IEC 60269 defines:
//   Inf = 1.25 × In : guaranteed NOT to blow within 1 hour (30°C reference)
//   If  = 1.60 × In : MUST blow within 1 hour
//
// Inf is a test point, not a rating for sustained load. Everything that
// protects the installation (planner, fuse guard) uses the nominal In,
// derated for temperature — never the Inf headroom.

// Returns the effective amps for a given fuse size.
// use_headroom=false: nominal amps (e.g. 25A → 25.0)   ← use this
// use_headroom=true:  1.15×In (e.g. 25A → 28.75). Short-term (<1 h) analysis
//                     only; NOT safe for sustained load. FUSE_USE_HEADROOM in
//                     config.h is false.
// Returns 0 if the fuse size is not a standard DIAZED size (16/20/25/35/50/63).
float fuse_effective_amps(int nominal_amps, bool use_headroom);

// Sustained, temperature-derated limit. Never exceeds nominal In:
//   factor = 1 - FUSE_TEMP_DERATE_PER_C × (T - FUSE_TEMP_REF_C),
//   clamped to [FUSE_TEMP_MIN_FACTOR, 1.0]
//   ≤30°C: 1.00×   40°C: 0.94×   50°C: 0.88×
// Implausible temperature (NaN, DS18B20 error codes -127 / 85, outside
// -55..125°C) → FUSE_TEMP_FAULT_FACTOR (fail-safe).
// Returns 0 for an invalid fuse size.
float fuse_effective_amps_temp(int nominal_amps, float temp_celsius);

// Available 3-phase power in kW for a given fuse, accounting for
// phase balance derating.
float fuse_max_power_kw(int nominal_amps, int phases, float voltage,
                        float phase_derating, bool use_headroom);

// Available power for charging after subtracting base household load.
// Returns 0 if base load already exceeds fuse capacity.
float fuse_available_charge_kw(int fuse_amps, int phases, float voltage,
                               float phase_derating, float base_load_kw,
                               bool use_headroom);

// Compute capped go-e charger amps (per phase) given available power budget.
// Returns 0 if not enough headroom for even minimum charging.
int fuse_goe_amps(float available_kw, int phases, float voltage,
                  int min_amps, int max_amps);

// Split one shared fuse budget between battery grid-charge and the EV.
// The battery request is served first (capped at available_kw); the EV gets
// whatever is left, converted to whole amps per phase. If the remainder is
// below min_amps the EV gets 0 = PAUSE (never a default/maximum current).
// Invariant: bat_kw + goe_amps × phases × voltage / 1000 ≤ available_kw.
struct FuseBudgetSplit {
    float bat_kw   = 0.0f;   // battery grid-charge power allowed (kW)
    int   goe_amps = 0;      // EV amps per phase, 0 = pause
};
FuseBudgetSplit fuse_split_budget(float available_kw, float bat_request_kw,
                                  bool ev_wants_charge, int phases, float voltage,
                                  int min_amps, int max_amps);
