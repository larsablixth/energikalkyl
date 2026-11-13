#pragma once

// bool is a built-in type in C++14 — no header needed

// ── Tibber Pulse — Real-time grid metering from HAN port ─────────────
// The Tibber Pulse sits on the electricity meter's HAN (Home Area Network)
// port and reports real-time per-phase current, voltage, and power.
//
// Data available via Tibber GraphQL API (subscription over websocket).
// For ESP32: we poll the REST endpoint periodically instead of streaming.

typedef struct {
    float power_w;            // total grid power (W), positive=import
    float power_l1_w;         // per-phase power (W)
    float power_l2_w;
    float power_l3_w;
    float current_l1_a;       // per-phase current (A)
    float current_l2_a;
    float current_l3_a;
    float voltage_l1_v;       // per-phase voltage (V)
    float voltage_l2_v;
    float voltage_l3_v;
    float accumulated_kwh;    // total import since midnight
    float accumulated_cost;   // total cost since midnight (SEK)
    float max_phase_a;        // highest per-phase current (for fuse check)
} TibberPulseData;

// Fetch latest Pulse measurement from Tibber API.
// token: Tibber API bearer token (from developer.tibber.com)
// Returns true if data was fetched successfully.
bool tibber_pulse_read(const char* token, TibberPulseData* data_out);

// Get the maximum per-phase current from the latest reading.
// This is the critical value for fuse protection — the DIAZED fuse
// on the heaviest loaded phase determines the limit, not the average.
float tibber_pulse_max_phase_amps(const TibberPulseData* data);
