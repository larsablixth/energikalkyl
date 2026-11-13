#pragma once
#include <cstdint>

// ── Slot Resolution ───────────────────────────────────────────────────────
// Price and scheduling granularity. Day-ahead prices are 15-minute (96 slots
// a day; 92 or 100 on the two daylight-saving days) or hourly. All per-slot
// arrays are sized to MAX_SLOTS.
//
// MAX_SLOTS was 1440 (1-minute prices, which the day-ahead market does not
// publish). That made every per-slot array 14× larger than needed and the
// firmware did not fit in the ESP32's static RAM (link error: .dram0.bss
// overflowed by ~42 KB). A price series with more than MAX_SLOTS slots is
// rejected as "no prices" (entsoe_parse_day), never truncated.
//
// Why constexpr instead of #define?
//   constexpr is a real typed constant — the compiler checks types, it
//   respects scope, and the debugger can show its value. #define is just
//   textual find-and-replace by the preprocessor — no type checking, no
//   scope, and it can cause subtle bugs (e.g. #define X 1+2 then X*3 = 7).
//   We keep #define only for strings and GPIO pins (Arduino macros need them).
constexpr int MAX_SLOTS            = 100;   // 15-min day incl. the 25-hour DST day
constexpr int DEFAULT_SLOT_MINUTES = 60;    // fallback when resolution unknown

// ── Network ────────────────────────────────────────────────────────────────
// W5500 SPI pins on NORVI ENET — kept as #define because Arduino pin macros
// expect preprocessor constants (digitalRead(pin) etc.)
#define ETH_CS_PIN       5
#define ETH_RESET_PIN    26
constexpr uint8_t ETH_MAC[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0x01};

// Strings stay as #define — constexpr const char* works in C++14 but
// some ESP-IDF APIs expect string literals, and #define is simpler here.
// The addresses below are the BUILT-IN values. They can be changed without
// rebuilding: controller_ip / gateway_ip / subnet_mask / dns_ip, deye_host,
// deye_port, goe_host and p1_host in /settings.txt on the SD card
// (settings.h, settings.example.txt).
#define CONTROLLER_IP    "192.168.1.50"
#define GATEWAY_IP       "192.168.1.1"
#define SUBNET_MASK      "255.255.255.0"
#define DNS_IP           "192.168.1.1"

// ── ENTSO-E ────────────────────────────────────────────────────────────────
#define ENTSOE_TOKEN     "YOUR_ENTSOE_TOKEN"
#define ENTSOE_DOMAIN    "10Y1001A1001A47J"   // SE3
// ENTSO-E is HTTPS-only. TLS via ESP_SSLClient (network_https_get), root CA
// in include/entsoe_ca.h (fails closed if the server's chain does not match).
#define ENTSOE_HOST      "web-api.tp.entsoe.eu"
constexpr int ENTSOE_PORT = 443;

// ── SMHI temperature forecast (for the house load model) ───────────────────
// Fetched together with tomorrow's prices (13:30) and for today at start-up.
// HTTPS; root CA in include/smhi_ca.h. If the fetch fails the plan uses the
// month's normal temperature (HOUSE_NORMAL_TEMP_C).
constexpr bool  SMHI_ENABLED = true;
#define SMHI_HOST        "opendata-download-metfcst.smhi.se"
constexpr int   SMHI_PORT    = 443;
// <-- YOUR location in decimal degrees (must be inside SMHI's forecast area:
// Sweden and its surroundings, otherwise SMHI answers "out of bounds").
constexpr float SMHI_LAT     = 59.3293f;   // Stockholm
constexpr float SMHI_LON     = 18.0686f;

// ── Money conventions (must match energikalkyl batteri.py / tariff.py) ────
// All money in SEK/kWh.
//   Spot prices (ENTSO-E / Nord Pool / elprisetjustnu) are EXCL. VAT.
//   Buying 1 kWh:  spot × SPOT_VAT_FACTOR + grid transfer fee + energy tax
//                  (grid fee and energy tax constants below are INCL. VAT)
//   Exporting 1 kWh (only if EXPORT_PRICE_FACTOR > 0):
//                  spot × EXPORT_PRICE_FACTOR − EXPORT_FEE_SEK, no VAT
//                  (private micro-producer), never below 0.
// Battery value per slot = E_out × buy_cost − E_in × buy_cost (zero-export:
// E_out capped at the house net load = load − solar).
constexpr float SPOT_VAT_FACTOR = 1.25f;    // 25% moms on spot when buying

// Energiskatt 2026: 36.0 öre + 25% moms = 45.0 öre/kWh (energikalkyl
// Tidstariff.energy_tax). Paid on every bought kWh, not on exported kWh.
constexpr float ENERGY_TAX_SEK  = 0.450f;

// ── Vattenfall Tidstariff 2026 (överföringsavgift, incl. VAT) ─────────────
// Höglasttid (peak):  winter months (Jan-Mar, Nov-Dec), weekdays 06-22,
//                     excl. holidays (tariff_is_holiday)  → 76.5 öre/kWh
// Övrig tid:          all other hours                     → 30.5 öre/kWh
constexpr float GRID_TRANSFER_HIGH_SEK = 0.765f;
constexpr float GRID_TRANSFER_LOW_SEK  = 0.305f;

// tariff_grid_fee() returns transfer fee + energy tax (like energikalkyl
// Tidstariff.total_cost_ore). The energy tax is INCLUDED here — do not add
// ENERGY_TAX_SEK again on top of GRID_FEE_*.
//   peak:     0.765 + 0.450 = 1.215 SEK/kWh
//   off-peak: 0.305 + 0.450 = 0.755 SEK/kWh
constexpr float GRID_FEE_HIGH   = GRID_TRANSFER_HIGH_SEK + ENERGY_TAX_SEK;
constexpr float GRID_FEE_LOW    = GRID_TRANSFER_LOW_SEK + ENERGY_TAX_SEK;

// Export (zero-export is the default: Deye "solar sell" off, no
// micro-producer contract). With 0 the planner never values export and the
// battery's discharge only counts up to the house net load.
constexpr float EXPORT_PRICE_FACTOR = 0.0f;   // energikalkyl export_price_factor
constexpr float EXPORT_FEE_SEK      = 0.05f;  // energikalkyl export_fee_ore = 5

// EUR → SEK for ENTSO-E prices (EUR/MWh → SEK/kWh = × EUR_SEK_RATE / 1000).
// Static for now; update periodically. HOOK (not implemented): fetch the ECB
// reference rate daily (e.g. frankfurter.app, as energikalkyl
// entsoe_source.py does) and pass it to entsoe_parse_day() instead of this
// constant. A wrong rate scales every price equally, so it changes the
// spot/fee balance but not the ranking of slots within a day.
constexpr float EUR_SEK_RATE    = 11.0f;

// ── Main Fuse (DIAZED) ────────────────────────────────────────────────────
// IEC 60269 gG "trög" — Swedish residential mains always use DIAZED fuses
constexpr int   FUSE_NOMINAL_AMPS   = 25;     // huvudsäkring size (16/20/25/35/50/63)
constexpr int   FUSE_PHASES         = 3;
constexpr float FUSE_VOLTAGE        = 230.0f;
constexpr float FUSE_PHASE_DERATING = 0.7f;   // phase balance derating factor
constexpr float BASE_LOAD_KW        = 3.0f;   // estimated household base load (kW)

// Headroom mode (IEC 60269 Inf = 1.25×In non-fusing current).
// Inf only guarantees the fuse will NOT blow for up to 1 hour at the 30°C
// reference temperature — it is not a rating for sustained operation, and
// cabinet temperature, ageing and contact resistance all eat into it.
// Battery charge windows (1-3 h) plus EV charging are sustained loads, so the
// planner and the fuse guard use the NOMINAL rating (what is printed on the
// fuse). Keep this false; the headroom path is kept only for analysis tools.
constexpr bool FUSE_USE_HEADROOM = false;

// ── Fuse Guard (real-time load shedding, see fuse_guard.h) ───────────────
// All percentages are relative to the SUSTAINED limit = nominal In (25 A),
// further reduced (never increased) by temperature derating. The guard looks
// at the highest of the three phase currents.
//   25 A fuse:  85% = 21.25 A   92% = 23.0 A   98% = 24.5 A   110% = 27.5 A
constexpr float FUSE_GOE_REDUCE_PCT  = 85.0f;   // level 1: reduce go-e amps
constexpr float FUSE_BAT_PAUSE_PCT   = 92.0f;   // level 2: pause battery grid-charge
constexpr float FUSE_HP_SHED_PCT     = 98.0f;   // level 3: pause go-e + shed pool HP
// Instantaneous hard trigger: a single reading at/above this jumps straight to
// level 3 (everything we control off). Below it, a level must be confirmed by
// FUSE_ESCALATE_CONFIRM_READINGS consecutive readings, so a motor inrush spike
// does not shed loads. gG fuses tolerate 1.25×In for an hour, 110% is far
// inside that, but we never want to sit there.
constexpr float FUSE_HARD_TRIP_PCT   = 110.0f;
constexpr int   FUSE_ESCALATE_CONFIRM_READINGS = 2;   // 2 × 5 s poll = 10 s

// Restore: step back ONE level only after the load has stayed below
// FUSE_RESTORE_PCT continuously for FUSE_RESTORE_HOLD_MS. The hold timer
// restarts after every step, so a full restore from level 3 takes ≥ 15 min.
// Any reading at/above FUSE_RESTORE_PCT restarts the timer (no oscillation).
constexpr float    FUSE_RESTORE_PCT     = 75.0f;
constexpr uint32_t FUSE_RESTORE_HOLD_MS = 5UL * 60UL * 1000UL;   // 5 min

// Meter fail-safe: if no VALID per-phase reading has arrived for this long
// (or none since boot), the guard enters a safe state: go-e limited to
// GOE_MIN_AMPS (or kept paused) and battery grid-charge paused, until fresh
// valid data returns (then normal hysteresis + hold time applies).
constexpr uint32_t FUSE_METER_STALE_MS  = 30UL * 1000UL;         // 30 s
// Plausibility window for a single phase current reading (A). Anything
// outside (or NaN) marks the whole reading invalid.
constexpr float    FUSE_METER_MAX_PLAUSIBLE_A = 200.0f;

// Deye EEPROM protection: the guard may PAUSE battery charging at any time
// (safety first), but a RESUME write is only sent if at least this long has
// passed since the guard's previous Deye write.
constexpr uint32_t FUSE_DEYE_MIN_WRITE_INTERVAL_MS = 10UL * 60UL * 1000UL;  // 10 min

// Temperature derating (only ever REDUCES the sustained limit):
//   factor = 1 - FUSE_TEMP_DERATE_PER_C × (T - FUSE_TEMP_REF_C), clamped to
//   [FUSE_TEMP_MIN_FACTOR, 1.0].  30°C → 1.00, 40°C → 0.94, 50°C → 0.88.
// An implausible sensor value (NaN, DS18B20 error codes -127/85, out of range)
// uses FUSE_TEMP_FAULT_FACTOR.
constexpr float FUSE_TEMP_REF_C        = 30.0f;
constexpr float FUSE_TEMP_DERATE_PER_C = 0.006f;   // 6% per 10°C
constexpr float FUSE_TEMP_MIN_FACTOR   = 0.70f;
constexpr float FUSE_TEMP_FAULT_FACTOR = 0.90f;

// ── Fuse Temperature Monitoring ──────────────────────────────────────────
// DS18B20 one-wire sensor near the DIAZED fuse for dynamic derating.
// Fan on a NORVI relay cools the cabinet when fuse gets warm.
// NOTE: the DS18B20 driver and fan relay are NOT wired yet (no OneWire
// library in lib_deps); the guard runs at nominal In until they are.
#define FUSE_TEMP_PIN        4      // DS18B20 data pin (GPIO 4)
#define FUSE_FAN_PIN         NORVI_RELAY4_PIN  // cabinet fan relay
constexpr float FUSE_TEMP_FAN_ON  = 40.0f;  // start fan above 40°C
constexpr float FUSE_TEMP_FAN_OFF = 35.0f;  // stop fan below 35°C (hysteresis)

// Resulting planning capacity with 25A fuse, 3-phase, 0.7 derating:
//   25.0A × 3 × 230V × 0.7 = 12.08 kW total, minus BASE_LOAD_KW (3.0)
//   = 9.08 kW shared between battery grid-charge and EV (see pipeline.cpp).

// ── Charge Strategy (ported from energikalkyl simulator) ───────────────────
// Minimum spread (discharge_value - charge_cost) to justify a cycle (SEK/kWh)
constexpr float MIN_SPREAD_SEK          = 0.20f;
constexpr float BATTERY_EFFICIENCY      = 0.90f;   // round-trip
// No "charge anyway" fallback: a day without a profitable pair (or a slot
// whose TOTAL buying cost is < 0) does not grid-charge at all.

// ── Looking ahead to tomorrow ──────────────────────────────────────────────
// The day is planned at midnight knowing nothing about tomorrow. When
// tomorrow's prices arrive (SCHEDULE_HOUR:MINUTE) the rest of today is
// re-planned with the value of energy still in the battery at midnight
// (bat_end_tranches): charge late today if tomorrow is dearer, and do not
// empty the battery into a cheap evening before an expensive morning.
// The program in the inverter is only replaced if the new one is expected
// to be worth at least PLAN_LOOKAHEAD_MIN_GAIN_SEK more for the rest of the
// day — most days it is not, and the inverter is then left alone.
constexpr bool  PLAN_LOOKAHEAD_ENABLED      = true;
constexpr float PLAN_LOOKAHEAD_MIN_GAIN_SEK = 1.0f;

// ── Expected house load and solar (planning inputs) ───────────────────────
// Load behind the Deye (what the battery can serve). The EV (go-e on its own
// circuit) is NOT in it — see EV section. Sources, first one available wins:
//   1. PipelineIO::forecast_load_kwh   an explicit load forecast (simulator)
//   2. the house model below at the forecast outdoor temperature
//      (PipelineIO::forecast_temp_c)
//   3. the house model below at the normal temperature of the month
//   4. HOUSE_LOAD_PROFILE_KW           only if HOUSE_LOAD_USE_WEATHER_MODEL
//                                      is false (the old behaviour)
//
// House model (house_load.h — energikalkyl heating.py): the load follows the
// outdoor temperature. These numbers are a CALIBRATION fitted from old
// consumption and weather data. They are energikalkyl's values for the
// reference house (fitted from 2024+2025 Tibber data); re-fit and replace
// them for another house or after changes to it.
constexpr bool  HOUSE_LOAD_USE_WEATHER_MODEL = true;
// Planning margin: the plan assumes this many times the house model's
// expected load. 1.0 = exactly the forecast. In the 3-year backtest 1.25
// earned about 80-100 kr more per year for 11-14 % more battery cycling —
// about 0.15-0.19 kr per extra kWh, just under MIN_SPREAD_SEK, hence 1.0
// here. Can be changed without rebuilding: load_plan_factor in
// /settings.txt on the SD card (settings.h, settings.example.txt).
constexpr float HOUSE_LOAD_PLAN_FACTOR = 1.0f;
#define SETTINGS_FILE        "/settings.txt"
constexpr float HOUSE_BASE_LOAD_KW     = 0.68f;   // non-heating load, kW
constexpr float HOUSE_DHW_KWH_PER_DAY  = 6.0f;    // hot water electricity, kWh/day
constexpr float HOUSE_H_LOSS_KW_PER_C  = 0.160f;  // heat loss, kW thermal per °C
constexpr float HOUSE_T_INDOOR_C       = 21.0f;   // indoor setpoint
constexpr float HOUSE_HP_COP_BASE      = 3.4f;    // heat pump COP at 0 °C outdoor
constexpr float HOUSE_HP_COP_SLOPE     = 0.056f;  // COP change per °C outdoor
constexpr float HOUSE_HP_COP_MIN       = 1.0f;
constexpr float HOUSE_HP_MAX_HEAT_KW   = 6.0f;    // heat pump max heat output
constexpr float HOUSE_ELPATRON_KW      = 3.0f;    // supplementary electric heater
// Normal outdoor temperature per month (Jan..Dec), °C — used when no
// temperature forecast is available. Mean of 2023-01..2026-03 at SMHI
// Stockholm-Arlanda (energikalkyl .weather_cache/arlanda_temp.csv).
constexpr float HOUSE_NORMAL_TEMP_C[12] = {
    -2.4f, -2.6f, 1.5f, 4.6f, 11.0f, 15.4f, 16.9f, 15.3f, 13.0f, 6.4f, 1.5f, -0.5f};
// Daily habit: kW above (+) or below (−) the model for each LOCAL hour
// 00..23, summing to zero over the day (evening cooking, night-time low…).
// All zero = the same load every hour. sim/calibrate_house prints this row
// from old data; a controller that has learned the house uses its own.
constexpr float HOUSE_HOUR_OFFSET_KW[24] = {
    0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
    0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};
constexpr float HOUSE_LOAD_MIN_KW = 0.1f;   // an expected load is never below this

// Learning the house from measurements (house_learn.h). Every user's house
// and habits differ: either calibrate the numbers above from old data
// (sim/calibrate_house), or let the controller learn them. The learned
// values replace HOUSE_BASE_LOAD_KW / HOUSE_H_LOSS_KW_PER_C / the hour
// offsets once enough days have been seen.
// The controller measures the house itself: the Deye's load power about once
// a minute (left out while the EV charges when the go-e is behind the Deye
// CT), with the SMHI forecast as that day's temperature. Each finished day
// is added to the fit and the result saved to the SD card.
constexpr bool  HOUSE_LEARN_ENABLED       = true;
constexpr int   HOUSE_SAMPLE_INTERVAL_S   = 60;     // seconds between load readings
#define HOUSE_LEARN_FILE     "/house.bin"            // learned state on the SD card
constexpr int   HOUSE_LEARN_MIN_DAYS      = 14;     // days before anything is used
constexpr float HOUSE_LEARN_MEMORY_DAYS   = 730.0f; // old days fade over ~2 years
// Heat loss is only fitted once the days differ enough in temperature:
// std-dev of the daily Σ ΔT/COP [°C·h]. 15 ≈ ±2 °C between days.
constexpr float HOUSE_LEARN_MIN_X_SPREAD  = 15.0f;
constexpr float HOUSE_LEARN_H_LOSS_MIN    = 0.02f;  // kW/°C: accepted range of a fit
constexpr float HOUSE_LEARN_H_LOSS_MAX    = 0.60f;
constexpr float HOUSE_LEARN_BASE_MIN_KW   = 0.10f;
constexpr float HOUSE_LEARN_BASE_MAX_KW   = 5.00f;

// Flat profile, kW per LOCAL hour: used only when HOUSE_LOAD_USE_WEATHER_MODEL
// is false. (BASE_LOAD_KW above remains the fuse reserve for the house and is
// not changed by the house model.)
constexpr float HOUSE_LOAD_PROFILE_KW[24] = {
    3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f,
    3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f, 3.0f};
// PV forecast default: energikalkyl's cos³ monthly model (solar.py) scaled
// to this array; PipelineIO::forecast_solar_kwh overrides it (simulator:
// PVGIS / real data; later: a weather forecast).
constexpr float SOLAR_KWP              = 15.0f;
constexpr float SOLAR_PERFORMANCE_RATIO = 0.85f;   // energikalkyl default

// ── Battery ────────────────────────────────────────────────────────────────
constexpr float BATTERY_CAPACITY_KWH = 64.0f;
constexpr float BATTERY_CHARGE_KW    = 15.0f;   // NKON hardware max (Deye limits to 12.5 kW)
constexpr float INVERTER_MAX_BAT_KW  = 12.5f;   // Deye 12K max battery throughput
constexpr int   BATTERY_MIN_SOC      = 15;       // %
constexpr int   BATTERY_MAX_SOC      = 95;       // %

// ── Deye Modbus ────────────────────────────────────────────────────────────
// Transport: raw Modbus TCP over the W5500 (ModbusEthernet, deye_modbus.cpp).
// OWNER DECISION: the stock Deye WiFi logger dongle speaks Solarman V5
// (proprietary framing around Modbus RTU) on TCP 8899, NOT raw Modbus TCP.
// Raw Modbus TCP needs either a Modbus-TCP gateway on the inverter's RS485
// port (e.g. Waveshare/USR RS485-to-Ethernet in "Modbus TCP ↔ RTU" mode) or
// the Deye LSE-3 Ethernet logger in Modbus-TCP mode. Solarman V5 is not
// implemented. Set host/port to whatever the gateway listens on (502 is the
// Modbus TCP default; 5200 is what the Python virtual_deye.py sim uses).
#define DEYE_HOST        "192.168.1.XXX"   // <-- Modbus TCP gateway IP
constexpr int DEYE_PORT      = 502;
constexpr int DEYE_MODBUS_ID = 1;

// Register map: include/deye_registers.h (3-phase SG04LP3 map, sources and
// VERIFY ON HARDWARE notes there).

// Program power outside charge windows (max battery power in self-use).
constexpr int   DEYE_PROG_IDLE_POWER_W   = 12000;   // SUN-12K rated
// Grid charge current (register 128) derived from the fuse-limited charge
// power: A = kW × 1000 × eff / V_charge_max (deye_grid_charge_current_a).
constexpr float BATTERY_CHARGE_V_MAX     = 57.6f;   // 16s LFP top of charge
constexpr float DEYE_INVERTER_EFF        = 0.96f;
constexpr int   DEYE_GRID_CHARGE_MAX_A   = 185;     // [K] limit, VERIFY on hardware

// Safe-state rules (pure decisions in plan_state.h):
// Consecutive failed Modbus transactions before the controller reverts to
// the safe program (and keeps retrying it until it is confirmed).
constexpr int      DEYE_MAX_CONSECUTIVE_FAILURES = 5;
// A plan with grid-charge windows older than this is cleared (safe program).
constexpr uint32_t PLAN_MAX_AGE_S       = 26UL * 3600UL;
// A day's plan expires at the end of that local day plus this grace.
constexpr uint32_t PLAN_EXPIRY_GRACE_S  = 15UL * 60UL;
// Boot: attempts to write + verify the safe program before tasks start.
constexpr int      DEYE_BOOT_SAFE_ATTEMPTS = 3;

// ── Grid meter (fuse guard input) ──────────────────────────────────────────
// HomeWizard P1 (local HTTP JSON on the HAN port) is the ONLY meter source in
// this build. Empty host = no meter = the fuse guard stays in its safe state.
#define HOMEWIZARD_P1_HOST   ""   // <-- P1 meter IP

// Tibber Pulse: DISABLED. liveMeasurement is only available as a GraphQL
// websocket subscription (wss://), and this build has no websocket client
// (and network_https_post() is not implemented). The code stays compiled;
// if enabled it can only fail → no reading → the fuse guard's safe state.
constexpr bool METER_TIBBER_PULSE_ENABLED = false;
#define TIBBER_TOKEN         ""   // <-- Tibber API token (only if enabled)
constexpr int TIBBER_POLL_MS = 10000;

// Easee monitor: DISABLED. Easee has no documented local API (cloud only).
// Its draw is seen in the P1 per-phase currents anyway, which is what the
// fuse guard acts on.
constexpr bool EASEE_MONITOR_ENABLED = false;
#define EASEE_HOST           ""   // <-- Easee charger IP (unused while disabled)

// ── go-e Charger (NORVI-controlled) ───────────────────────────────────────
#define GOE_HOST         "192.168.1.YYY"   // <-- go-e IP
constexpr int GOE_PORT     = 80;
constexpr int GOE_MAX_AMPS = 16;
constexpr int GOE_MIN_AMPS = 6;

// EV scheduling (decoupled from the battery plan; energikalkyl EV default):
// the EV charges in the cheapest slots whose local start hour is in
// [EV_WINDOW_START_H, EV_WINDOW_END_H) (wraps midnight) until EV_DAILY_KWH.
constexpr int   EV_WINDOW_START_H = 18;
constexpr int   EV_WINDOW_END_H   = 7;
constexpr float EV_DAILY_KWH      = 30.0f;
// Shared fuse budget between battery grid-charge and EV, per slot:
//   EV_PRIO_BATTERY_FIRST  battery plan first, the EV gets the remainder
//   EV_PRIO_EV_FIRST       EV plan first, the battery only gets what it leaves
//   EV_PRIO_AUTO           plan the day both ways and keep the cheaper one
//                          (EV energy cost − battery plan value; the EV must
//                          get its EV_DAILY_KWH, ties → battery first)
// OWNER DECISION (2026-11): "whatever is the most profitable" → AUTO.
enum EvPriorityMode : uint8_t {
    EV_PRIO_BATTERY_FIRST = 0,
    EV_PRIO_EV_FIRST      = 1,
    EV_PRIO_AUTO          = 2,
};
constexpr EvPriorityMode EV_PRIORITY_MODE = EV_PRIO_AUTO;

// Is the go-e behind the Deye grid CT? OWNER ANSWER (2026-11): YES — the
// Deye CT sees everything, including the go-e. In self-use the Deye then
// discharges the battery into EV charging like any other load. Used by:
//   plan_shared_day   EV plan per slot is part of the load the battery
//                     planner sees (both orders; battery first re-plans the
//                     battery once the EV slots are known), so discharge into
//                     EV slots is valued and HOLD segments (SOC floor at the
//                     planned level) keep cheap-night EV charging on the grid
//   surplus_task      the Deye grid reading already includes the EV draw:
//                     never subtracted again (false: the go-e draw is read
//                     from the charger and subtracted)
// false = previous behaviour (load excludes the EV, SELF never serves it).
constexpr bool DEYE_CT_SEES_GOE = true;

// EV battery
constexpr float EV_CAPACITY_KWH = 77.0f;
constexpr float EV_TARGET_SOC   = 80.0f;   // normal charge target (%)
constexpr float EV_CONFLICT_SOC = 50.0f;   // reduced target when fuse conflict

// ── Flex Loads ────────────────────────────────────────────────────────────
constexpr int MAX_FLEX_LOADS   = 4;
constexpr int FLEX_CTRL_GPIO   = 0;   // NORVI relay pin
constexpr int FLEX_CTRL_SHELLY = 1;   // Shelly smart plug via REST
constexpr int FLEX_CTRL_TUYA   = 2;   // Tuya local protocol (TCP port 6669)

// NORVI ENET-AE06-T relay outputs (verify against datasheet)
#define NORVI_RELAY1_PIN     12
#define NORVI_RELAY2_PIN     14
#define NORVI_RELAY3_PIN     27
#define NORVI_RELAY4_PIN     33

// Shelly smart plug IPs (set per load, "" if GPIO)
#define SHELLY1_HOST         ""
#define SHELLY2_HOST         ""

// ── Pool Heat Pump (Tuya) ─────────────────────────────────────────────
// Mountfield BP-100 HS, controlled via Tuya local protocol (Boost Core app)
// Get device_id and local_key using: python3 -m tinytuya wizard
#define POOL_HP_TUYA_IP      "192.168.1.ZZZ"   // <-- pool pump WiFi IP
#define POOL_HP_TUYA_ID      "YOUR_DEVICE_ID"   // 20-char alphanumeric
#define POOL_HP_TUYA_KEY     "YOUR_LOCAL_KEY"    // 16-char hex from tinytuya
constexpr float POOL_HP_POWER_KW = 1.9f;        // 8.3A × 230V

// ── Solar Surplus Monitoring ──────────────────────────────────────────────
constexpr int   SURPLUS_POLL_MS   = 30000;  // poll Deye every 30 seconds
constexpr float SURPLUS_MIN_KW    = 0.5f;   // minimum surplus to activate flex load
constexpr float EV_SURPLUS_MIN_KW = 1.4f;   // minimum surplus for EV (~6A × 230V)
constexpr int   HYSTERESIS_POLLS  = 2;      // consecutive polls before toggling (2 × 30s)

// Deye live-data registers: include/deye_registers.h

// ── Schedule Timing ────────────────────────────────────────────────────────
// 13:30 local: fetch TOMORROW's prices and compute tomorrow's plan. On
// failure retry every PRICE_RETRY_INTERVAL_MIN until PRICE_RETRY_DEADLINE_MIN;
// after that tomorrow runs the safe program (no grid charging).
constexpr int SCHEDULE_HOUR   = 13;
constexpr int SCHEDULE_MINUTE = 30;
constexpr int PRICE_RETRY_INTERVAL_MIN = 15;
constexpr int PRICE_RETRY_DEADLINE_MIN = 23 * 60;     // 23:00 local

// ── Time ───────────────────────────────────────────────────────────────────
// The DS3231 holds UTC. Local time only via localtime_r() with this TZ.
#define LOCAL_TZ_POSIX   "CET-1CEST,M3.5.0,M10.5.0/3"   // Europe/Stockholm
#define NTP_HOST         "pool.ntp.org"
constexpr int      NTP_PORT            = 123;
constexpr uint16_t NTP_LOCAL_UDP_PORT  = 8888;            // our source port
constexpr uint32_t NTP_RESYNC_S        = 6UL * 3600UL;   // every 6 h
constexpr uint32_t NTP_TIMEOUT_MS      = 2000;
// System time before this year = not set (RTC lost power, no NTP) → the
// controller refuses to plan and holds the safe program. An unset clock reads
// 1970 (ESP32) or 2000 (DS3231), so 2020 catches it and still lets the
// simulator / energikalkyl replay price history from 2020 on (was 2025, which
// held every 2023-2024 backtest day on the safe program).
constexpr int      TIME_MIN_VALID_YEAR = 2020;

// ── Display ────────────────────────────────────────────────────────────────
#define OLED_SDA_PIN     21
#define OLED_SCL_PIN     22
constexpr int OLED_ADDRESS = 0x3C;

// ── SD Card ────────────────────────────────────────────────────────────────
#define SD_CS_PIN        15
#define LOG_FILE         "/schedule.log"
