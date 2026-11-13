#pragma once
// Pure (hardware-free) Deye program logic: window → 6-point program mapping,
// HHMM conversion, safe program, register diff for write/verify, live-data
// decoding. Unit-tested natively (test/test_deye_program). The Modbus
// transport lives in deye_modbus.cpp.

#include <cstdint>
#include "deye_registers.h"
#include "tou_window.h"

// One complete Deye system-work-mode program (registers 128..177 subset).
struct DeyeProgram {
    uint16_t time_hhmm[DEYE_N_PROGRAMS] = {};   // 148..153
    uint16_t power_w[DEYE_N_PROGRAMS]   = {};   // 154..159
    uint16_t soc[DEYE_N_PROGRAMS]       = {};   // 166..171
    uint16_t charge[DEYE_N_PROGRAMS]    = {};   // 172..177 (bit0 = grid)
    uint16_t tou_enable         = DEYE_TOU_ENABLE_ALL_DAYS;  // 146
    uint16_t grid_charge_enable = 0;            // 130
    uint16_t grid_charge_current_a = 0;         // 128, 0 = leave unchanged
};

struct DeyeRegWrite {
    uint16_t addr;
    uint16_t value;
};

// Max registers one program writes: 6×4 + 146 + 130 + 128.
constexpr int DEYE_PROGRAM_MAX_WRITES = DEYE_N_PROGRAMS * 4 + 3;

// Minute of day → Deye HHMM. 1440 (end of day) and anything ≥ 1440 wraps to
// 0000 (the next program point at midnight); negative clamps to 0000.
// 855 → 1415, 1380 → 2300, 1440 → 0.
uint16_t deye_min_to_hhmm(int minute_of_day);

// HHMM → minute of day, -1 if not a valid time (hh > 23 or mm > 59).
int deye_hhmm_to_min(uint16_t hhmm);

// Map up to MAX_TOU_WINDOWS charge windows onto the six program points.
//   - inside a window: grid charge ON, SOC = window target (clamped to
//     [min_soc, 100]), power = window charge_power_w (or idle_power_w if 0)
//   - outside: grid charge OFF, SOC = min_soc (discharge floor), power =
//     idle_power_w — i.e. normal self-use
// Windows may touch (merged if settings are equal), may end at 1440 and may
// cross midnight (end_min < start_min). Unused points are filled by splitting
// the longest segment (same settings → no behaviour change). A point at 0000
// is always present when fewer than six boundaries are needed; with three
// separate windows not touching midnight, Prog6 wraps through midnight.
// grid_charge_enable (130) = 1 iff any window is programmed.
// Returns false (out untouched) for overlapping or out-of-range windows or
// n_windows > MAX_TOU_WINDOWS. Empty windows (start == end) are ignored.
bool deye_build_program(const TouWindow* windows, int n_windows,
                        int min_soc, int idle_power_w, int grid_charge_current_a,
                        DeyeProgram* out);

// Program segments (planner output, tou_window.h) → program points.
// segs[0].start_min must be 0, starts strictly increasing, n_segs ≤ 6.
// Per segment: grid charge bit, SOC clamped to [min_soc, 100], power
// (0 → idle_power_w). Equal neighbours are merged, unused points padded.
// grid_charge_enable (130) = 1 iff any segment charges from the grid.
bool deye_build_program_segments(const ProgSegment* segs, int n_segs,
                                 int min_soc, int idle_power_w, int grid_charge_current_a,
                                 DeyeProgram* out);

// The known safe program: no grid charging anywhere, TOU enabled every day,
// SOC floor = min_soc all day, power = idle_power_w, grid charge enable = 0.
// (Grid charge current is left unchanged.)
void deye_safe_program(int min_soc, int idle_power_w, DeyeProgram* out);

// True if any program point allows grid charging or 130 is set.
bool deye_program_grid_charges(const DeyeProgram* p);

// All register writes that make up the program, in write order (130 first
// when DISABLING grid charge, last when enabling, so the inverter never sees
// a half-written charge program with charging enabled). Returns count.
int deye_program_writes(const DeyeProgram* p, DeyeRegWrite* out, int max_out);

// Compare the program with a register block read from the inverter
// (block[i] = register base + i). Writes the registers that differ (or lie
// outside the block) to out, returns their count. Used both to skip
// unchanged EEPROM writes and to verify the read-back.
int deye_program_diff(const DeyeProgram* p, const uint16_t* block,
                      uint16_t base, int len, DeyeRegWrite* out, int max_out);

// Grid charge current (register 128, A) for a fuse-limited charge power:
//   A = floor(kw × 1000 × inverter_eff / v_charge_max), clamped [1, max_a].
// v_charge_max is the highest battery voltage during charging, so the AC
// side never exceeds kw. kw ≤ 0 → 0 (= leave unchanged / no charge).
int deye_grid_charge_current_a(float kw, float v_charge_max, float inverter_eff, int max_a);

// ── Live data ───────────────────────────────────────────────────────────
struct DeyeLiveData {
    float battery_soc     = 0.0f;  // %
    float battery_power_w = 0.0f;  // Deye raw sign: + discharge, − charge (VERIFY)
    float grid_l1_w = 0.0f, grid_l2_w = 0.0f, grid_l3_w = 0.0f;  // + import (VERIFY)
    float grid_power_w    = 0.0f;  // total, + import, − export (VERIFY)
    float load_power_w    = 0.0f;
    float pv_power_w      = 0.0f;  // PV1 + PV2
};

// Decode the live block (block[i] = register DEYE_LIVE_BLOCK_BASE + i,
// len ≥ DEYE_LIVE_BLOCK_LEN). Returns false for an implausible reading
// (SOC > 100, load < 0, PV > 30 kW) — never a silent zero.
bool deye_decode_live(const uint16_t* block, int len, DeyeLiveData* out);
