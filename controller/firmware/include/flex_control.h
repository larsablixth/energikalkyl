#pragma once

// bool is a built-in type in C++14 — no header needed
#include "tuya_client.h"

// ── Flex Load Control ─────────────────────────────────────────────────
// Controls flex loads via NORVI relay GPIO, Shelly smart plugs, or
// Tuya local protocol (for devices like the Mountfield pool heat pump).

// Initialize GPIO pins for relay control (call once at startup).
void flex_control_init_gpio(void);

// Set a flex load ON or OFF.
// control_type: FLEX_CTRL_GPIO, FLEX_CTRL_SHELLY, or FLEX_CTRL_TUYA
// gpio_pin: relevant only for FLEX_CTRL_GPIO
// shelly_ip: relevant only for FLEX_CTRL_SHELLY
// tuya_dev: relevant only for FLEX_CTRL_TUYA (NULL for other types)
// on: true = activate, false = deactivate
bool flex_control_set(int control_type, int gpio_pin,
                      const char* shelly_ip, const TuyaDevice* tuya_dev,
                      bool on);
