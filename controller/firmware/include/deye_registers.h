#pragma once
// ── Deye SUN-12K-SG04LP3 (3-phase LV hybrid) Modbus register map ─────────
//
// ONE table for every Deye register this firmware touches. Holding
// registers, function code 0x03 (read) / 0x06 (write single), unit id
// DEYE_MODBUS_ID. Addresses are DECIMAL (hex in the comment).
//
// Sources (all public, read 2026-11):
//   [K]  kellerza/sunsynk — src/sunsynk/definitions/three_phase_common.py
//        and three_phase_lv.py (Sunsynk/Deye 3-phase LV)
//        https://github.com/kellerza/sunsynk/blob/main/src/sunsynk/definitions/three_phase_common.py
//        https://github.com/kellerza/sunsynk/blob/main/src/sunsynk/definitions/three_phase_lv.py
//        (sunsynk convention: a NEGATIVE factor means "signed int16", the
//        magnitude is the scale — see src/sunsynk/sensors.py)
//   [S]  StephanJoubert/home_assistant_solarman — deye_sg04lp3.yaml
//        https://github.com/StephanJoubert/home_assistant_solarman/blob/main/custom_components/solarman/inverter_definitions/deye_sg04lp3.yaml
//   [D]  davidrapan/ha-solarman — deye_p3.yaml (Deye 3-phase family)
//        https://github.com/davidrapan/ha-solarman/blob/main/custom_components/solarman/inverter_definitions/deye_p3.yaml
//
// Only registers that at least TWO of these sources place at the same
// address with the same meaning are used. Anything else is marked
// "VERIFY ON HARDWARE" below and in the table (verified = false).
//
// The previous map in config.h (SOC 103, grid 169, load 175, PV 186,
// "TOU1 start/end 148/149") was the SINGLE-PHASE map; on the SG04LP3
// 103 is "battery low voltage" and 169/175 are Prog4 SOC / Prog4 charge.
//
// ── System work mode program ("Time of Use", 6 program points) ─────────
// Deye does not have "charge windows". It has SIX chained program points:
//   Prog N is active from ProgN_TIME until Prog(N+1)_TIME; Prog6 runs until
//   Prog1_TIME (wraps through midnight) — [K] models the times as a circular
//   chain (PROG1_TIME.min = PROG6_TIME). Times are HHMM (0000..2359; 2400
//   does not exist — end of day is the next point at 0000).
// Each point has:
//   TIME   (148..153)  HHMM
//   POWER  (154..159)  W, max battery power in that period
//   SOC    (166..171)  %, battery target: with grid charge ON the inverter
//                      charges from grid up to this SOC; with it OFF the
//                      battery is not discharged below this SOC.
//   CHARGE (172..177)  bit0 = allow grid charge, bit1 = allow generator
//                      charge ([K]: bitmask 0x03, [D]: 0=Disabled 1=Grid
//                      2=Generator 3=Both).
// Plus:
//   146  bit0 = Time-of-use enable, bits1..7 = Mon..Sun ([K] + [D]:
//        0xFF = enabled every day).
//   130  global "grid charge enabled" ([K] "Grid Charge enabled",
//        [D] "Battery Grid Charging"). Must be 1 for per-program grid
//        charging; we keep it 0 whenever no charge window is programmed so
//        that the "Grid Charging Start SOC" (127) path cannot charge either.
//   128  grid charge current, A ([K] "Grid Charge Battery current" max 185,
//        [D] "Battery Grid Charging Current").
//
// ── Live data scaling / signs (3-phase) ──────────────────────────────────
//   588 battery SOC        %   uint16           [K] [S] [D]
//   590 battery power      W   int16            [K] [S] [D]
//        SIGN VERIFY ON HARDWARE: Deye raw value, community reports
//        + = discharging, − = charging ([D] exposes an "inverse" attribute).
//   622..624 grid L1..L3   W   int16            [K] [D]
//   625 grid total         W   int16 (low word; high word 690 only matters
//        above ±32.7 kW, impossible on a 25 A fuse)  [K] [S] [D]
//        SIGN VERIFY ON HARDWARE: assumed + = import, − = export.
//   653 load total         W   int16 (low word, high 659)  [K] [S] [D]
//   672 PV1 / 673 PV2      W   uint16           [K] [S] [D]
//        [D] lists scale [1, 10] for some (HV / large) models: the
//        SG04LP3 LV is scale 1 per [K] and [S]. VERIFY ON HARDWARE.
//
// Registers we READ but never WRITE (owner sets them at commissioning;
// logged at boot): 141 energy pattern, 142 work mode, 145 solar sell.

#include <cstdint>

// ── Control (read/write) ─────────────────────────────────────────────────
constexpr uint16_t DEYE_REG_GRID_CHARGE_CURRENT = 128;  // 0x0080 A          [K][D]
constexpr uint16_t DEYE_REG_GRID_CHARGE_ENABLE  = 130;  // 0x0082 0/1        [K][D]
constexpr uint16_t DEYE_REG_ENERGY_PATTERN      = 141;  // 0x008D read only  [K][D]
constexpr uint16_t DEYE_REG_WORK_MODE           = 142;  // 0x008E read only  [K][D]
constexpr uint16_t DEYE_REG_SOLAR_SELL          = 145;  // 0x0091 read only  [K][D]
constexpr uint16_t DEYE_REG_TOU_ENABLE          = 146;  // 0x0092 bitmask    [K][D]
constexpr uint16_t DEYE_REG_PROG_TIME_BASE      = 148;  // 0x0094..0x0099    [K][D]
constexpr uint16_t DEYE_REG_PROG_POWER_BASE     = 154;  // 0x009A..0x009F    [K][D] (scale: VERIFY)
constexpr uint16_t DEYE_REG_PROG_SOC_BASE       = 166;  // 0x00A6..0x00AB    [K][D]
constexpr uint16_t DEYE_REG_PROG_CHARGE_BASE    = 172;  // 0x00AC..0x00B1    [K][D]

constexpr int      DEYE_N_PROGRAMS              = 6;
constexpr uint16_t DEYE_TOU_ENABLE_ALL_DAYS     = 0x00FF;  // bit0 enable + Mon..Sun
constexpr uint16_t DEYE_PROG_CHARGE_GRID        = 0x0001;  // bit0
// Bits 2..5 of 172..177 (mode / "sell") exist only in [K] — VERIFY ON
// HARDWARE. We write the whole register as 0 or 1, i.e. those bits are
// cleared (no battery selling in any program).

// Control block read in ONE transaction for diff + read-back verify.
constexpr uint16_t DEYE_CTRL_BLOCK_BASE = 128;
constexpr uint16_t DEYE_CTRL_BLOCK_LEN  = 50;    // 128..177

// ── Live data (read only) ────────────────────────────────────────────────
constexpr uint16_t DEYE_REG_BATTERY_SOC   = 588;  // 0x024C %   uint16  [K][S][D]
constexpr uint16_t DEYE_REG_BATTERY_POWER = 590;  // 0x024E W   int16   [K][S][D] sign VERIFY
constexpr uint16_t DEYE_REG_GRID_L1_POWER = 622;  // 0x026E W   int16   [K][D]
constexpr uint16_t DEYE_REG_GRID_L2_POWER = 623;  // 0x026F W   int16   [K][D]
constexpr uint16_t DEYE_REG_GRID_L3_POWER = 624;  // 0x0270 W   int16   [K][D]
constexpr uint16_t DEYE_REG_GRID_POWER    = 625;  // 0x0271 W   int16   [K][S][D] sign VERIFY
constexpr uint16_t DEYE_REG_LOAD_POWER    = 653;  // 0x028D W   int16   [K][S][D]
constexpr uint16_t DEYE_REG_PV1_POWER     = 672;  // 0x02A0 W   uint16  [K][S][D] scale VERIFY
constexpr uint16_t DEYE_REG_PV2_POWER     = 673;  // 0x02A1 W   uint16  [K][S][D] scale VERIFY

// Live block read in ONE transaction (86 registers, < 125 FC03 limit).
constexpr uint16_t DEYE_LIVE_BLOCK_BASE = 588;
constexpr uint16_t DEYE_LIVE_BLOCK_LEN  = 86;    // 588..673

// ── Table (documentation + unit-test sanity: no duplicate addresses) ─────
enum DeyeRegAccess : uint8_t { DEYE_RO = 0, DEYE_RW = 1 };

struct DeyeRegDef {
    uint16_t      addr;
    uint8_t       count;      // consecutive registers (programs: 6)
    DeyeRegAccess access;
    bool          is_signed;
    float         scale;      // engineering value = raw × scale
    bool          verified;   // false = only one source / sign or scale unsure
    const char*   name;
};

constexpr DeyeRegDef DEYE_REG_TABLE[] = {
    {DEYE_REG_GRID_CHARGE_CURRENT, 1, DEYE_RW, false, 1.0f, true,  "grid_charge_current_a"},
    {DEYE_REG_GRID_CHARGE_ENABLE,  1, DEYE_RW, false, 1.0f, true,  "grid_charge_enable"},
    {DEYE_REG_ENERGY_PATTERN,      1, DEYE_RO, false, 1.0f, true,  "energy_pattern"},
    {DEYE_REG_WORK_MODE,           1, DEYE_RO, false, 1.0f, true,  "work_mode"},
    {DEYE_REG_SOLAR_SELL,          1, DEYE_RO, false, 1.0f, true,  "solar_sell"},
    {DEYE_REG_TOU_ENABLE,          1, DEYE_RW, false, 1.0f, true,  "tou_enable_days"},
    {DEYE_REG_PROG_TIME_BASE,      6, DEYE_RW, false, 1.0f, true,  "prog_time_hhmm"},
    {DEYE_REG_PROG_POWER_BASE,     6, DEYE_RW, false, 1.0f, false, "prog_power_w"},       // scale VERIFY
    {DEYE_REG_PROG_SOC_BASE,       6, DEYE_RW, false, 1.0f, true,  "prog_soc_pct"},
    {DEYE_REG_PROG_CHARGE_BASE,    6, DEYE_RW, false, 1.0f, true,  "prog_charge_bits"},
    {DEYE_REG_BATTERY_SOC,         1, DEYE_RO, false, 1.0f, true,  "battery_soc_pct"},
    {DEYE_REG_BATTERY_POWER,       1, DEYE_RO, true,  1.0f, false, "battery_power_w"},    // sign VERIFY
    {DEYE_REG_GRID_L1_POWER,       1, DEYE_RO, true,  1.0f, true,  "grid_l1_power_w"},
    {DEYE_REG_GRID_L2_POWER,       1, DEYE_RO, true,  1.0f, true,  "grid_l2_power_w"},
    {DEYE_REG_GRID_L3_POWER,       1, DEYE_RO, true,  1.0f, true,  "grid_l3_power_w"},
    {DEYE_REG_GRID_POWER,          1, DEYE_RO, true,  1.0f, false, "grid_power_w"},       // sign VERIFY
    {DEYE_REG_LOAD_POWER,          1, DEYE_RO, true,  1.0f, true,  "load_power_w"},
    {DEYE_REG_PV1_POWER,           1, DEYE_RO, false, 1.0f, false, "pv1_power_w"},        // scale VERIFY
    {DEYE_REG_PV2_POWER,           1, DEYE_RO, false, 1.0f, false, "pv2_power_w"},        // scale VERIFY
};
constexpr int DEYE_REG_TABLE_LEN = static_cast<int>(sizeof(DEYE_REG_TABLE) / sizeof(DEYE_REG_TABLE[0]));
