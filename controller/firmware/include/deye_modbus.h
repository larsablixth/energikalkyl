#pragma once
// Deye SUN-12K-SG04LP3 over raw Modbus TCP (W5500 / ModbusEthernet).
// Register map: deye_registers.h. Program logic (pure): deye_program.h.
//
// Every program write: read control block → write only registers that
// differ (EEPROM wear) → read back → retry mismatches once → report.
// All access holds the shared bus lock (bus_lock.h).

#include "deye_program.h"

// Read battery SOC (register 588, %). False if no valid reply.
bool deye_read_soc(float* soc_out);

// Write a complete program with read-back verification. force_verify=false
// skips all Modbus traffic if the cached (verified) program is identical.
bool deye_write_program(const DeyeProgram* program, bool force_verify);

// Charge windows (local minutes) → 6-point program (deye_build_program with
// BATTERY_MIN_SOC floor, DEYE_PROG_IDLE_POWER_W) → deye_write_program.
// grid_charge_current_a: register 128 (0 = leave unchanged).
bool deye_set_charge_windows(const TouWindow* windows, int n_windows,
                             int grid_charge_current_a);

// Planner program segments (≤ 6, first at 00:00) → deye_build_program_segments
// → deye_write_program. grid_charge_current_a: register 128 (0 = unchanged).
bool deye_set_program_segments(const ProgSegment* segs, int n_segs,
                               int grid_charge_current_a);

// Single window [start_min, end_min) (grid reward override).
bool deye_set_charge(int start_min, int end_min, int target_soc);

// Safe program: no grid charging, self-use, SOC floor BATTERY_MIN_SOC.
// Used for idle, fuse-guard pause, stale plan, invalid time, boot.
bool deye_set_idle(void);

// Same as deye_set_idle() but always reads back (boot, safe-state entry).
bool deye_apply_safe_program(void);

// Forget the verified-program cache: the next write is not skipped and reads
// back again (daily rewrite, after Modbus failures). The verified grid-charge
// state (deye_grid_charge_enabled) is kept until a write starts.
void deye_invalidate_cache(void);

// ── Real-time monitoring ─────────────────────────────────────────────
using DeyePowerStatus = DeyeLiveData;   // pv/grid/load + SOC, battery, phases

// One block read of registers 588..673 + decode. False on any failure.
bool deye_read_power_status(DeyePowerStatus* status_out);
// Same read for background sampling (house learning): a FAILED read here does
// not add to deye_consecutive_failures(), so sampling once a minute does not
// make the safety fallback ("repeated Modbus failures") trip sooner than the
// controller's own reads would. A successful read still clears the counter.
bool deye_sample_power_status(DeyePowerStatus* status_out);

// True unless the last VERIFIED program had no grid charging (unknown — none
// verified yet, or a write in progress / failed — counts as charging,
// conservative for the fuse guard and the safe-state check).
bool deye_grid_charge_enabled(void);

// Consecutive failed transactions (0 after any success).
int deye_consecutive_failures(void);

// Read (not write) the owner-set mode registers for the boot log.
bool deye_read_modes(uint16_t* energy_pattern, uint16_t* work_mode, uint16_t* solar_sell);
