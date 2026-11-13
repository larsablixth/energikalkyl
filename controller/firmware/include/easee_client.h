#pragma once

// bool is a built-in type in C++14 — no header needed

// ── Easee EV Charger — Local API reader ──────────────────────────────
// Reads real-time per-phase current from the Easee charger.
// The Easee has its own CT clamp and reports per-phase data.
// Tibber controls it; the NORVI only monitors for fuse protection.
//
// API: Easee uses SignalR (websocket) for real-time, but also has
// a REST-like local API on port 80 when on the same network.
// Alternatively: Easee Cloud API (api.easee.com) with OAuth.
//
// For local access without cloud: the Easee exposes a simple
// HTTP endpoint when accessed from the local network.

typedef struct {
    float current_l1_a;      // per-phase current drawn by charger
    float current_l2_a;
    float current_l3_a;
    float total_power_kw;    // total charge power
    int   state;             // 1=standby, 2=paused, 3=charging, 4=complete
    bool  is_charging;
    float session_kwh;       // energy this session
} EaseeStatus;

// Read current status from Easee charger on local network.
// host: IP address of the Easee charger
// Returns true if status was read successfully.
bool easee_read_status(const char* host, EaseeStatus* status_out);

// Get the maximum per-phase current drawn by the Easee.
float easee_max_phase_amps(const EaseeStatus* status);
