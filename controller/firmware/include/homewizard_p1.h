#pragma once

// bool is a built-in type in C++14 — no header needed

// ── HomeWizard P1 Meter — Local HAN port reader ─────────────────────
// Reads real-time per-phase current and power from the electricity
// meter via a HomeWizard P1 device on the local network.
//
// No cloud dependency — direct HTTP GET to the device's local API.
// Response time: <100ms on LAN. Falls back to this when Tibber Pulse
// API is slow or unavailable.
//
// API: GET http://<ip>/api/v1/data
// Returns JSON with per-phase current, voltage, power, and totals.

typedef struct {
    float total_power_w;       // active import power (W)
    float total_power_export_w; // active export power (W)
    float current_l1_a;
    float current_l2_a;
    float current_l3_a;
    float voltage_l1_v;
    float voltage_l2_v;
    float voltage_l3_v;
    float total_energy_import_kwh;
    float total_energy_export_kwh;
} HomeWizardP1Data;

// Read latest measurement from HomeWizard P1 on local network.
// host: IP address of the P1 device (e.g. "192.168.1.42")
// Returns true if data was read successfully.
bool homewizard_p1_read(const char* host, HomeWizardP1Data* data_out);

// Parse and validate a /api/v1/data response (pure, unit-testable).
// Returns true only if http_status == 200, all three active_current_lX_a
// keys are present and numeric, |I| ≤ HOMEWIZARD_MAX_PLAUSIBLE_A, and any
// voltages given are 150-280 V (absent voltages default to 230 V).
// Currents are stored as absolute values (export can be reported negative).
// On failure *data_out is left unchanged.
constexpr float HOMEWIZARD_MAX_PLAUSIBLE_A = 200.0f;
bool homewizard_p1_parse(const char* json, int http_status, HomeWizardP1Data* data_out);

// Get the maximum per-phase current.
float homewizard_p1_max_phase_amps(const HomeWizardP1Data* data);
