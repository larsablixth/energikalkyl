#pragma once
// Where the simulated devices live, for wasm/controller_hal.cpp:
//   - interactive (default): the JS world through sim_hal.h (hal_* → Module.hal)
//   - whole-period runs (wasm/runner.cpp): the C++ world (world.h)
// Same signatures as sim_hal.h, so the device emulation (driver behaviour)
// in controller_hal.cpp is one piece of code for both.
#include <cstdint>
#include "sim_hal.h"

struct SimDevices {
    bool (*read_soc)(float* soc)                                                   = nullptr;
    int  (*fetch_prices)(int y, int m, int d, float* out, int max_slots, int* slot_min) = nullptr;
    bool (*forecast)(int which, double day_start_utc, int slot_min, int n, int month, float* out) = nullptr;
    bool (*write_program)(const uint16_t* regs)                                    = nullptr;
    bool (*read_live)(HalLive* out)                                                = nullptr;
    bool (*read_meter)(HalMeter* out)                                              = nullptr;
    bool (*goe_status)(HalGoe* out)                                                = nullptr;
    bool (*goe_set_amps)(int amps)                                                 = nullptr;
    bool (*flex_set)(int index, bool on)                                           = nullptr;
    void (*log)(const char* level, const char* msg)                                = nullptr;
    void (*display)(const char* l1, const char* l2, const char* l3, const char* l4) = nullptr;
};

/** Use these devices (nullptr = the JS world). Call before ctrl_reset. */
void sim_set_devices(const SimDevices* d);
