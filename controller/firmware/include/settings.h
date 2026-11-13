#pragma once
// Settings that can be changed WITHOUT rebuilding the firmware: a small text
// file on the SD card (SETTINGS_FILE, "/settings.txt"), read once at
// start-up. Pure parser (no hardware) — unit-tested natively
// (test/test_settings). See settings.example.txt.
//
//   # comment
//   deye_host = 192.168.1.60
//   load_plan_factor = 1.25
//
// Every setting has a default from config.h; the file only needs the lines
// you want to change. A line that is not understood, names an unknown
// setting or holds a value outside its allowed range is IGNORED (and
// reported) — the default stays. A missing file means all defaults.
// Decimal comma is accepted for numbers (1,25).

#include "config.h"

constexpr int SETTINGS_IP_LEN = 16;      // "255.255.255.255" + NUL

struct RuntimeSettings {
    // ── This controller on the network (static address) ──────────────────
    char controller_ip[SETTINGS_IP_LEN] = CONTROLLER_IP;
    char gateway_ip[SETTINGS_IP_LEN]    = GATEWAY_IP;
    char subnet_mask[SETTINGS_IP_LEN]   = SUBNET_MASK;
    char dns_ip[SETTINGS_IP_LEN]        = DNS_IP;

    // ── Devices the controller talks to ──────────────────────────────────
    char deye_host[SETTINGS_IP_LEN] = DEYE_HOST;            // inverter Modbus TCP gateway
    int  deye_port                  = DEYE_PORT;            // 1 … 65535
    char goe_host[SETTINGS_IP_LEN]  = GOE_HOST;             // go-e car charger
    char p1_host[SETTINGS_IP_LEN]   = HOMEWIZARD_P1_HOST;   // HomeWizard P1 meter;
                                                            // empty = no meter

    // ── Planning ─────────────────────────────────────────────────────────
    // The plan uses this many times the expected house load (house model
    // only). 1.0 = exactly the forecast; above 1 charges somewhat more than
    // the forecast needs, which earned more in the backtest at the price of
    // more battery cycling. Allowed 0.5 … 3.0.
    float load_plan_factor = HOUSE_LOAD_PLAN_FACTOR;
    // Location for the SMHI temperature forecast, decimal degrees.
    float smhi_lat = SMHI_LAT;
    float smhi_lon = SMHI_LON;

    // ── The installation (plant.h; applied with settings_apply_plant) ────
    float battery_kwh    = BATTERY_CAPACITY_KWH;   // usable capacity
    float inverter_kw    = INVERTER_MAX_BAT_KW;    // battery charge/discharge via the inverter
    int   fuse_amps      = FUSE_NOMINAL_AMPS;      // main fuse
    float base_load_kw   = BASE_LOAD_KW;           // house reserve on the fuse
    float ev_kwh_per_day = EV_DAILY_KWH;           // 0 = no EV planned
    float solar_kwp      = SOLAR_KWP;
    float grid_fee_high  = GRID_FEE_HIGH;          // SEK/kWh incl. energy tax, high-load time
    float grid_fee_low   = GRID_FEE_LOW;           // other time (= high for a flat tariff)
};

struct SettingsReport {
    int  applied = 0;             // lines that changed a setting
    int  ignored = 0;             // lines not understood / out of range
    char first_problem[80] = {};  // the first ignored line (for the log)
};

// Parse the text of a settings file into *s (which should hold the defaults
// on entry). text may be null (= nothing to apply). Returns rep->applied.
// Addresses must be IPv4 in dotted form (192.168.1.60); only p1_host may be
// left empty ("p1_host =") to switch that device off.
int settings_parse(const char* text, RuntimeSettings* s, SettingsReport* rep);

// True if s is an IPv4 address in dotted form: four numbers 0-255.
// (The config.h placeholders such as "192.168.1.XXX" are not.)
bool settings_ip_valid(const char* s);

// The settings in force. Filled once in setup() (before the network starts
// and before any task runs) and only read afterwards.
const RuntimeSettings& runtime_settings(void);
RuntimeSettings* runtime_settings_mutable(void);

struct Plant;
// Copy the installation values of the settings into the plant (plant.h).
void settings_apply_plant(const RuntimeSettings& s, Plant* p);
