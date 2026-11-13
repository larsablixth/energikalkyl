#pragma once

// ── Charge windows (firmware side of the Deye program) ───────────────────
// The planner produces up to MAX_TOU_WINDOWS grid-charge windows per day in
// LOCAL wall-clock minutes. deye_build_program() (deye_program.h) maps them
// onto the Deye's six chained program points.
constexpr int MAX_TOU_WINDOWS = 3;

struct TouWindow {
    int start_min      = 0;   // inclusive, local minutes from midnight (0..1439)
    int end_min        = 0;   // exclusive, 1..1440 (1440 = end of day). If
                              // end_min < start_min the window crosses midnight.
    int target_soc     = 0;   // charge to this SOC (%)
    int charge_power_w = 0;   // program power during the window, 0 = default
};

// ── Program segments (planner output, deye_build_program_segments) ───────
// The whole local day as ≤ DEYE_N_PROGRAMS consecutive segments, the first
// starting at 00:00. Each segment: grid charge on/off + SOC (target when
// charging, discharge floor otherwise — a high floor HOLDS the battery for
// later, expensive hours) + battery power limit.
constexpr int MAX_PROG_SEGMENTS = 6;

struct ProgSegment {
    int  start_min   = 0;      // local minute 0..1439, strictly increasing
    bool grid_charge = false;
    int  soc         = 0;      // %
    int  power_w     = 0;      // 0 = default (idle power)
};
