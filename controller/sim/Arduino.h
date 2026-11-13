#pragma once
// Minimal <Arduino.h> for the simulator build (WASM + native driver).
// Only firmware/src/surplus_task.cpp includes it, and the simulator uses just
// its pure surplus_eval_load(); surplus_task_func (the FreeRTOS loop) is
// compiled but never called. Definitions live in wasm/hal_stubs.cpp.
#include <cstdint>
#include <cstddef>
typedef uint32_t TickType_t;
#define pdMS_TO_TICKS(ms) (static_cast<TickType_t>(ms))
void vTaskDelay(TickType_t ticks);
unsigned long millis(void);
