#pragma once

// bool is a built-in type in C++14 — no header needed
#include <cstdint>

// ── Tuya Local Protocol v3.3 Client ──────────────────────────────────
// Controls Tuya-based smart devices (like pool heat pumps) over the
// local network. No cloud dependency — uses the Tuya TCP protocol
// on port 6669 with AES-128-ECB encryption.
//
// The Mountfield BP-100 HS pool heat pump uses the "Boost Core" app
// which is a Tuya white-label. Standard Tuya DPS:
//   DP 1: Power on/off (bool)
//   DP 2: Target temperature (int, ×10)
//   DP 3: Current water temperature (int, ×10, read-only)
//   DP 4: Mode (enum: "heat", "cool", "auto")
//
// To get the local_key, use tinytuya's wizard with a Tuya IoT
// developer account (free, one-time setup).

constexpr int TUYA_PORT          = 6669;
constexpr int TUYA_KEY_LEN       = 16;    // AES-128 key length
constexpr int TUYA_MAX_ID_LEN    = 24;
constexpr int TUYA_MAX_IP_LEN    = 16;
constexpr int TUYA_TIMEOUT_MS    = 5000;

typedef struct {
    char device_id[TUYA_MAX_ID_LEN];
    char local_key[TUYA_KEY_LEN + 1];  // 16-byte hex key + null
    char ip[TUYA_MAX_IP_LEN];
} TuyaDevice;

// Send a boolean DPS command (e.g. DP 1 = power on/off).
// Returns true if the device acknowledged.
bool tuya_set_bool(const TuyaDevice* dev, int dp, bool value);

// Send an integer DPS command (e.g. DP 2 = temperature × 10).
bool tuya_set_int(const TuyaDevice* dev, int dp, int value);

// Convenience: turn device on/off (DP 1).
bool tuya_power(const TuyaDevice* dev, bool on);

// Query device status. Returns true if reachable.
// status_out: JSON string of current DPS values (caller provides buffer).
bool tuya_get_status(const TuyaDevice* dev, char* status_out, int buf_len);
